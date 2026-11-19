#!/usr/bin/env python3
"""Install the hash-locked historical external CLI without network access."""
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

root = Path('/opt/task-dependencies/jj')
lock = json.loads((root / 'jj-lock.json').read_text())
archive = root / lock['source_url'].rsplit('/', 1)[-1]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == lock['sha256']
with tarfile.open(archive) as bundle:
    member = bundle.getmember(lock['member'])
    assert member.isfile() and Path(member.name).name == 'jj'
    binary = bundle.extractfile(member).read()
    assert hashlib.sha256(binary).hexdigest() == lock['binary_sha256']
    target = Path('/usr/local/bin/jj')
    target.write_bytes(binary)
    target.chmod(0o755)
    license_member = bundle.getmember('./LICENSE')
    assert license_member.isfile()
    (root / 'LICENSE').write_bytes(bundle.extractfile(license_member).read())
version = subprocess.check_output([str(target), '--version'], text=True, timeout=10).strip()
assert version.startswith('jj ' + lock['version'] + '-')
print(version)
