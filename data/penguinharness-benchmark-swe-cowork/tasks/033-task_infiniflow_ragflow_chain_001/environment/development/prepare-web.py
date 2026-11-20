"""Prepare pinned Node and baseline-locked frontend dependencies for export."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path('/opt/ragflow-web-prepared')
ROOT.mkdir(exist_ok=True)
version = '22.16.0'
archive_name = f'node-v{version}-linux-x64.tar.xz'
sources = [f'https://nodejs.org/dist/v{version}/', f'https://npmmirror.com/mirrors/node/v{version}/']
errors = []
for source in sources:
    try:
        with urllib.request.urlopen(source + 'SHASUMS256.txt', timeout=45) as response:
            sums = response.read(200_000).decode()
        expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == archive_name)
        assert re.fullmatch('[0-9a-f]{64}', expected)
        archive = ROOT / archive_name
        with urllib.request.urlopen(source + archive_name, timeout=120) as response, archive.open('wb') as output:
            copied = 0
            while chunk := response.read(1024 * 1024):
                copied += len(chunk)
                if copied > 100_000_000:
                    raise ValueError('Node archive exceeds the declared size bound')
                output.write(chunk)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        assert actual == expected, (actual, expected)
        with tarfile.open(archive) as data:
            data.extractall(ROOT, filter='data')
        (ROOT / f'node-v{version}-linux-x64').rename(ROOT / 'node')
        archive.unlink()
        provenance = {'node_version': version, 'node_archive_sha256': expected, 'node_source': source + archive_name}
        print(json.dumps(provenance), flush=True)
        break
    except Exception as exc:
        errors.append(f'{source}: {type(exc).__name__}: {exc}')
        print(errors[-1], flush=True)
else:
    raise RuntimeError('Cannot obtain pinned Node archive: ' + '; '.join(errors))

work = Path('/opt/ragflow-web-install')
work.mkdir(exist_ok=True)
for name in ['package.json', 'package-lock.json']:
    shutil.copyfile(Path('/opt/ragflow-web-inputs') / name, work / name)
provenance['package_json_sha256'] = hashlib.sha256((work / 'package.json').read_bytes()).hexdigest()
provenance['package_lock_sha256'] = hashlib.sha256((work / 'package-lock.json').read_bytes()).hexdigest()
env = dict(os.environ, PATH=str(ROOT / 'node/bin') + ':' + os.environ['PATH'])
env.update(npm_config_cache='/opt/ragflow-web-npm-cache', npm_config_audit='false', npm_config_fund='false', npm_config_update_notifier='false')
result = subprocess.run([str(ROOT / 'node/bin/npm'), 'ci', '--no-audit', '--no-fund'], cwd=work, env=env, timeout=1500)
if result.returncode:
    # Use the public npm registry with identical versions and SRI checks.
    # Only the installation copy changes; the baseline lock is retained.
    lock = json.loads((work / 'package-lock.json').read_text())
    for item in lock['packages'].values():
        url = item.get('resolved', '')
        if url.startswith('https://registry.npmmirror.com/'):
            item['resolved'] = url.replace('https://registry.npmmirror.com/', 'https://registry.npmjs.org/', 1)
    (work / 'package-lock.json').write_text(json.dumps(lock) + '\n')
    subprocess.run([str(ROOT / 'node/bin/npm'), 'ci', '--no-audit', '--no-fund', '--registry=https://registry.npmjs.org'], cwd=work, env=env, timeout=1500, check=True)
(work / 'node_modules').rename(ROOT / 'node_modules')
(ROOT / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2) + '\n')
shutil.rmtree('/opt/ragflow-web-npm-cache', ignore_errors=True)
print('PINNED WEB DEPENDENCIES READY', flush=True)
