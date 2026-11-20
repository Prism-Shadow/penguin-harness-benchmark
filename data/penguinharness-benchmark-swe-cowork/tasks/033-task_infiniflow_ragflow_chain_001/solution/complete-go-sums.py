import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile


def checksum(value):
    if not isinstance(value, str) or not value.startswith('h1:'):
        raise ValueError('missing canonical Go checksum')
    if len(base64.b64decode(value[3:], validate=True)) != 32:
        raise ValueError('invalid Go checksum')
    return value


def read_sums(text):
    entries = {}
    for line in text.splitlines():
        path, version, digest = line.split()
        key = (path, version)
        if key in entries and entries[key] != digest:
            raise ValueError('conflicting existing Go checksums')
        entries[key] = checksum(digest)
    return entries


def serialize(entries):
    return ''.join(f'{path} {version} {entries[path, version]}\n'
                   for path, version in sorted(entries))


def complete_graph(repo, manifest, entries, environment):
    with tempfile.NamedTemporaryFile(prefix='.ragflow-sums-', suffix='.mod', dir=repo) as temporary:
        shadow = Path(temporary.name)
        shadow_sums = shadow.with_suffix('.sum')
        shadow.write_bytes(manifest)
        try:
            shadow_sums.write_text(serialize(entries))
            subprocess.run(['go', 'list', '-mod=mod', '-modfile=' + str(shadow), '-m', 'all'],
                           cwd=repo, env=environment, capture_output=True, text=True,
                           timeout=120, check=True)
            completed = read_sums(shadow_sums.read_text())
            if any(completed.get(key) != digest for key, digest in entries.items()):
                raise ValueError('graph checksum conflicts with pinned go.sum')
            return completed
        finally:
            shadow_sums.unlink(missing_ok=True)


def complete(repo):
    repo = Path(repo).resolve()
    manifest = repo / 'go.mod'
    sums = repo / 'go.sum'
    original_manifest = manifest.read_bytes()
    original_sums = sums.read_bytes()
    environment = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off',
                       GOSUMDB='sum.golang.org', GOMAXPROCS='2', GOENV='off',
                       GOAUTH='off', GOWORK='off', GO111MODULE='on', GOFLAGS='',
                       GOPRIVATE='', GONOPROXY='', GONOSUMDB='', GOINSECURE='')

    def invoke(arguments, directory):
        result = subprocess.run(['go', *arguments], cwd=directory, env=environment,
                                capture_output=True, text=True, timeout=120, check=True)
        return json.loads(result.stdout)

    metadata = invoke(['mod', 'edit', '-json'], repo)
    replacements = {(item['Old']['Path'], item['Old'].get('Version', '')): item['New']
                    for item in metadata.get('Replace') or []}
    known = read_sums(original_sums.decode())
    additions = {}
    with tempfile.TemporaryDirectory(prefix='ragflow-sums-') as directory:
        for requirement in metadata.get('Require') or []:
            path, version = requirement['Path'], requirement['Version']
            replacement = replacements.get((path, version), replacements.get((path, '')))
            if replacement:
                if not replacement.get('Version'):
                    continue
                path, version = replacement['Path'], replacement['Version']
            if all((path, version + suffix) in known for suffix in ('', '/go.mod')):
                continue
            downloaded = invoke(['mod', 'download', '-json', path + '@' + version], directory)
            if downloaded.get('Error') or downloaded.get('Path') != path or downloaded.get('Version') != version:
                raise ValueError('Go download identity or verification failed')
            for suffix, field in [('', 'Sum'), ('/go.mod', 'GoModSum')]:
                key = (path, version + suffix)
                digest = checksum(downloaded.get(field))
                if key in known and known[key] != digest:
                    raise ValueError('verified checksum conflicts with pinned go.sum')
                if key not in known:
                    additions[key] = digest
    if manifest.read_bytes() != original_manifest or sums.read_bytes() != original_sums:
        raise ValueError('module inputs changed during checksum completion')
    combined = complete_graph(repo, original_manifest, {**known, **additions}, environment)
    if manifest.read_bytes() != original_manifest or sums.read_bytes() != original_sums:
        raise ValueError('module inputs changed during checksum completion')
    if combined != known:
        sums.write_text(serialize(combined))
    print(f'Completed {len(combined) - len(known)} checksum entries from verified offline modules; go.mod unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='/app/code')
    complete(parser.parse_args().repo)
