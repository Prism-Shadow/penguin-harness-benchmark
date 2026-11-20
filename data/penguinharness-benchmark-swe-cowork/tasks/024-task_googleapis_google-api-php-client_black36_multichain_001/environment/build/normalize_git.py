"""Keep exactly the frozen commit and tree; remove later refs and unreachable code."""
import os
from pathlib import Path
import shutil
import subprocess

repo = Path('/app/code')
base = '90166261e9e460f30d021f6c78fc661bbfc51c06'

def git(*args, data=None, env=None):
    return subprocess.run(['git', '-c', 'safe.directory=/app/code', '-C', str(repo), *args],
                          input=data, capture_output=True, check=True, env=env).stdout

head = git('rev-parse', 'HEAD').decode().strip()
assert head == base, (head, base)
assert not git('diff', '--name-only', base, '--'), 'image code differs from frozen commit'
# Keep the exact original baseline ID, but no parent trees, refs or later blobs.
objects = {base}
objects.update(git('rev-list', '--objects', '--no-object-names', base + '^{tree}').decode().split())
records = [(oid, git('cat-file', '-t', oid).decode().strip(), git('cat-file', '-p', oid))
           for oid in sorted(objects)]
# cat-file -p renders trees; trees need their raw binary content instead.
records = [(oid, kind, git('cat-file', kind, oid)) for oid, kind, _ in records]
oldgit = repo / '.git'
shutil.rmtree(oldgit)
git('init', '-q')
for oid, kind, data in records:
    written = git('hash-object', '-w', '-t', kind, '--stdin', data=data).decode().strip()
    assert oid == written
(oldgit / 'shallow').write_text(base + '\n')
git('update-ref', 'refs/heads/baseline', base)
git('symbolic-ref', 'HEAD', 'refs/heads/baseline')
git('reset', '--mixed', base)
for path in [oldgit, *oldgit.rglob('*')]:
    os.chmod(path, 0o755 if path.is_dir() else 0o644)
print('Frozen Git normalized:', base, 'objects:', len(records))
