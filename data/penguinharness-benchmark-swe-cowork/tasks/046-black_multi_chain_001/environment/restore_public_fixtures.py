"""Restore exactly the hash-bound original test fixtures lost during Git cleaning."""
import argparse
import hashlib
import json
from pathlib import Path
import os


def restore(repository, seed):
    repository = repository.resolve(strict=True)
    seed = seed.resolve(strict=True)
    manifest = json.loads((seed / 'manifest.json').read_text())
    staged = []
    for record in manifest['files']:
        relative = Path(record['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[:2] != ('tests', 'data'):
            raise ValueError('Not a public test fixture: ' + str(relative))
        source = seed / relative
        target = repository / relative
        if source.is_symlink() or not source.resolve().is_relative_to(seed):
            raise ValueError('Fixture seed escapes source: ' + str(relative))
        if target.is_symlink() or not target.resolve().is_relative_to(repository):
            raise ValueError('Fixture target escapes worktree: ' + str(relative))
        content = source.read_bytes()
        if len(content) != record['bytes'] or hashlib.sha256(content).hexdigest() != record['sha256']:
            raise ValueError('Fixture content hash mismatch: ' + str(relative))
        if target.exists() and target.read_bytes() != content:
            raise ValueError('Refusing to replace a modified fixture: ' + str(relative))
        staged.append((target, content, record['mode']))
    for target, content, mode in staged:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        os.chmod(target, mode)
    print(json.dumps({'restored': len(staged), 'source_archive_sha256': manifest['source_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('repository', type=Path)
    parser.add_argument('seed', type=Path)
    args = parser.parse_args()
    restore(args.repository, args.seed)
