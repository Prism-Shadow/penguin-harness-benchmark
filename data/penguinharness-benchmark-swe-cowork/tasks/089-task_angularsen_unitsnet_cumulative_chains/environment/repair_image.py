"""Make the frozen baseline usable without DAC capabilities; remove nonbaseline Git history."""
import os
import shutil
from pathlib import Path
import subprocess

repo = Path('/app/code')
base = '300694e45aa4703c7d85c3392937c58f75313084'

def git(*args):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + str(repo), '-C', str(repo), *args], text=True).strip()

assert git('rev-parse', 'HEAD') == base
refs = git('for-each-ref', '--format=%(refname)').splitlines()
print('Pruning non-baseline Git references:', len(refs))
git('checkout', '--detach', base)
for ref in refs:
    git('update-ref', '-d', ref)
git('reflog', 'expire', '--expire=now', '--all')
(repo / '.git/shallow').write_text(base + '\n')
for name in ('ORIG_HEAD', 'FETCH_HEAD'):
    (repo / '.git' / name).unlink(missing_ok=True)
# Build a new object store from exactly this commit and its tree. Existing
# archives can contain kept packs, for which gc --prune=now leaves old objects.
objects = {base, git('rev-parse', base + '^{tree}')}
objects.update(git('ls-tree', '-r', '-t', '--format=%(objectname)', base).splitlines())
pack_path = Path('/opt/task-build/baseline.pack')
with pack_path.open('wb') as output:
    subprocess.run(['git', '-c', 'safe.directory=' + str(repo), '-C', str(repo),
                    'pack-objects', '--stdout'], input=('\n'.join(sorted(objects))+'\n').encode(),
                   stdout=output, check=True)
shutil.rmtree(repo / '.git/objects')
(repo / '.git/objects').mkdir()
with pack_path.open('rb') as source:
    subprocess.run(['git', '-c', 'safe.directory=' + str(repo), '-C', str(repo),
                    'index-pack', '--stdin'], stdin=source, check=True)
pack_path.unlink()
assert git('cat-file', '--batch-all-objects', '--batch-check=%(objecttype)').splitlines().count('commit') == 1
assert git('rev-list', '--all', 'HEAD') == base
for path in (repo, *repo.rglob('*')):
    if path.is_symlink():
        continue
    # The solver runs as root with capabilities dropped. Tar's uid=1000,
    # mode=0600 Git objects otherwise remain unreadable even to that process.
    os.chown(path, 0, 0)
    path.chmod(path.stat().st_mode | 0o600 | (0o100 if path.is_dir() else 0))
print('Baseline Git object/read/write closure repaired:', base)
