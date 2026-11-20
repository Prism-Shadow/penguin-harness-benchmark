"""Install the authenticated, pinned documentation generator without networking."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

source, destination = map(Path, sys.argv[1:])
lock = json.loads((source / 'tool-lock.json').read_text())
assert lock['name'] == 'terraform-docs' and lock['version'] == '0.16.0'
archive = source / lock['filename']
assert hashlib.sha256(archive.read_bytes()).hexdigest() == lock['sha256']
checksums = (source / 'terraform-docs-v0.16.0.sha256sum').read_bytes()
assert hashlib.sha256(checksums).hexdigest() == lock['checksums_sha256']
assert any(line.split()[0] == lock['sha256'] and line.split()[-1].lstrip('*') == archive.name for line in checksums.decode().splitlines())
with tarfile.open(archive) as bundle:
    entry = next(m for m in bundle.getmembers() if m.name.lstrip('./') == 'terraform-docs')
    assert entry.isfile() and entry.size < 64 * 1024 * 1024
    destination.write_bytes(bundle.extractfile(entry).read())
destination.chmod(0o755)
print('CODEGEN_TOOL_INSTALLED terraform-docs 0.16.0 sha256=' + lock['sha256'])
