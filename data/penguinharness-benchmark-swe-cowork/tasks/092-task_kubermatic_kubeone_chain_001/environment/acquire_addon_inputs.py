"""Acquire only official, versioned public addon inputs during image building."""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
import yaml

ROOT = Path(sys.argv[1])
LIMIT = 32 * 1024 * 1024

def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                value = response.read(LIMIT + 1)
            if len(value) > LIMIT: raise ValueError('oversized upstream input')
            return value
        except (OSError, TimeoutError):
            if attempt == 2: raise
            time.sleep(1)

def write(name, body):
    (ROOT / name).write_bytes(body)
    return hashlib.sha256(body).hexdigest()

records = []
for name, version, repo in [
    ('cloud-provider-azure', '1.29.0+20240201', 'https://raw.githubusercontent.com/kubernetes-sigs/cloud-provider-azure/master/helm/repo'),
    ('azuredisk-csi-driver', 'v1.29.5', 'https://raw.githubusercontent.com/kubernetes-sigs/azuredisk-csi-driver/master/charts'),
]:
    index_url = repo + '/index.yaml'
    index = get(index_url)
    entries = yaml.safe_load(index)['entries'][name]
    matches = [e for e in entries if e['version'].lstrip('v') == version.lstrip('v')]
    print(name, 'selected version', version, flush=True)
    entry = matches[0]
    url = urllib.parse.urljoin(repo + '/', entry['urls'][0])
    body = get(url)
    digest = hashlib.sha256(body).hexdigest()
    if digest != entry['digest']: raise ValueError('official Helm digest mismatch: ' + name)
    filename = name + '-' + version + '.tgz'
    write(filename, body)
    records.append(dict(id=name, version=version, path=filename, url=url, sha256=digest,
                        repository=repo, verification=dict(method='official-helm-index-sha256',
                        index_url=index_url, index_sha256=hashlib.sha256(index).hexdigest())))
api = 'https://api.github.com/repos/vmware/cloud-director-named-disk-csi-driver'
commit = json.loads(get(api + '/commits/1.6.0'))['sha']
tree = json.loads(get(api + '/git/trees/' + commit + '?recursive=1'))
assert tree.get('truncated') is False
for name in ['csi-controller.yaml', 'csi-driver.yaml', 'csi-node.yaml']:
    entry = next(e for e in tree['tree'] if e['path'] == 'manifests/' + name)
    url = 'https://raw.githubusercontent.com/vmware/cloud-director-named-disk-csi-driver/' + commit + '/manifests/' + name
    body = get(url)
    assert hashlib.sha1(('blob ' + str(len(body)) + '\0').encode() + body).hexdigest() == entry['sha']
    filename = 'vcd-1.6.0-' + name
    digest = write(filename, body)
    records.append(dict(id='vcd-' + name, version='1.6.0', path=filename, url=url, sha256=digest,
                        reference='https://raw.githubusercontent.com/vmware/cloud-director-named-disk-csi-driver/1.6.0/manifests/' + name,
                        verification=dict(method='official-source-commit-and-git-blob', commit=commit, blob=entry['sha'])))
(ROOT / 'additional-lock.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps(records, indent=2))
