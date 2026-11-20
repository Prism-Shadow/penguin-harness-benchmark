import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


PROXIES = ('https://goproxy.cn', 'https://goproxy.io', 'https://proxy.golang.org')
PROBE_MODULE = 'github.com/cloudwego/eino'


def validate_proxy(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(character.isspace() or character in ',|\\' for character in value)):
        raise ValueError('Go proxy must be one credential-free HTTPS URL, without fallback directives')
    return value.rstrip('/')


def probe_target(repo):
    matched = re.search(r'^\s*' + re.escape(PROBE_MODULE) + r'\s+(v\S+)',
                        (repo / 'go.mod').read_text(), re.MULTILINE)
    if not matched:
        raise ValueError('Missing pinned Go probe module')
    version = matched.group(1)
    expected = {}
    for line in (repo / 'go.sum').read_text().splitlines():
        module, revision, digest = line.split()
        if module == PROBE_MODULE and revision in (version, version + '/go.mod'):
            key = 'Sum' if revision == version else 'GoModSum'
            if key in expected or not digest.startswith('h1:'):
                raise ValueError('Invalid or duplicate pinned Go probe checksum')
            expected[key] = digest
    if len(expected) != 2:
        raise ValueError('Both pinned module and go.mod checksums are required')
    return version, expected


def select_proxy(repo, proxies, temporary_root, runner=subprocess.run):
    proxies = [validate_proxy(proxy) for proxy in proxies]
    version, expected = probe_target(repo)
    failures = []
    for proxy in proxies:
        with tempfile.TemporaryDirectory(prefix='ragflow-go-proxy-', dir=temporary_root) as directory:
            temporary = Path(directory)
            isolated = temporary / 'probe'
            isolated.mkdir()
            environment = dict(os.environ, GOENV='off', GOAUTH='off', GO111MODULE='on',
                               GOTOOLCHAIN='local', GOWORK='off',
                               GOFLAGS='-modcacherw', GOPROXY=proxy,
                               GOSUMDB='sum.golang.org ' + proxy + '/sumdb/sum.golang.org',
                               GOINSECURE='', GOPRIVATE='', GONOSUMDB='', GONOPROXY='',
                               GOMAXPROCS='2', GOMEMLIMIT='3GiB', HOME=str(temporary / 'home'),
                               GOMODCACHE=str(temporary / 'modules'), GOCACHE=str(temporary / 'build'))
            command = ['go', 'mod', 'download', '-json', PROBE_MODULE + '@' + version]
            try:
                result = runner(command, cwd=isolated, env=environment, capture_output=True,
                                text=True, timeout=180)
            except subprocess.TimeoutExpired:
                error = 'Go proxy verification timed out after 180 seconds'
            else:
                if result.returncode == 0:
                    record = json.loads(result.stdout)
                    if (record.get('Error') or record.get('Path') != PROBE_MODULE
                            or record.get('Version') != version
                            or any(record.get(key) != digest for key, digest in expected.items())):
                        raise RuntimeError('Go proxy probe disagrees with pinned go.sum: ' + proxy)
                    return {
                        'schema': 'ragflow-go-proxy-verification-v1',
                        'proxy': proxy, 'sumdb': environment['GOSUMDB'],
                        'module': PROBE_MODULE, 'version': version, **expected,
                        'go_mod_sha256': hashlib.sha256((repo / 'go.mod').read_bytes()).hexdigest(),
                        'go_sum_sha256': hashlib.sha256((repo / 'go.sum').read_bytes()).hexdigest(),
                        'verification': 'fresh-cache Go download with TLS and canonical sumdb signature verification',
                        'failed_probes': failures,
                    }
                error = (result.stderr + result.stdout).strip()[-8192:]
            failures.append({'proxy': proxy, 'error': error})
            print('Rejected Go proxy ' + proxy + ': ' + error, file=sys.stderr, flush=True)
    raise RuntimeError('No verified HTTPS Go proxy/sumdb endpoint; restore build DNS/CA/proxy routing. '
                       'Do not disable certificate or checksum verification.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--temporary-root', type=Path, default=Path('/tmp'))
    parser.add_argument('--proxy', action='append')
    args = parser.parse_args()
    if args.receipt.exists():
        raise RuntimeError('Refusing to overwrite an existing proxy verification receipt')
    override = os.environ.get('RAGFLOW_GOPROXY')
    proxies = args.proxy or ([override] if override else PROXIES)
    receipt = select_proxy(args.repo, proxies, args.temporary_root)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['proxy'])


if __name__ == '__main__':
    main()
