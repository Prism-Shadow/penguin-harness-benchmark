"""Validate a separately acquired Android dependency closure before installation."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

REQUIRED_VERSIONS = {'gradle': '9.5.0', 'agp': '9.2.1', 'sdk_platform': '36.1',
                     'java': '17', 'rust': '1.89.0'}


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def unpack(archive, destination, expected):
    assert sha256(archive) == expected, 'Android closure archive hash mismatch'
    destination = Path(destination)
    assert not destination.exists(), 'Closure destination must be fresh'
    with tarfile.open(archive) as bundle:
        for entry in bundle.getmembers():
            path = PurePosixPath(entry.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert entry.isfile() or entry.isdir() or entry.issym(), 'Special/archive hardlink forbidden'
            if entry.issym():
                link = PurePosixPath(entry.linkname)
                assert not link.is_absolute()
                combined = path.parent.joinpath(link)
                depth = 0
                for part in combined.parts:
                    depth += -1 if part == '..' else 0 if part == '.' else 1
                    assert depth >= 0, 'Escaping symlink'
        destination.mkdir(parents=True)
        bundle.extractall(destination, filter='data')
    validate_inventory(destination)


def validate_inventory(root):
    root = Path(root)
    manifest = json.loads((root / 'closure.json').read_text())
    assert manifest['schema'] == 'repair070-android-closure-v1'
    assert all(str(manifest['versions'].get(k)) == v for k, v in REQUIRED_VERSIONS.items()), 'Required tool versions differ'
    assert manifest.get('seed_kind') == 'unsolved-baseline'
    assert manifest.get('seed_revision') == '7d87bab895b92a753c72ffba7957fa2d45fa85cc'
    files = manifest.get('files')
    assert isinstance(files, dict) and files, 'Missing complete dependency inventory'
    observed = {}
    for p in sorted(root.rglob('*')):
        if p.name == 'closure.json' and p.parent == root:
            continue
        if p.is_symlink():
            assert p.resolve().is_relative_to(root.resolve())
            observed[p.relative_to(root).as_posix()] = {'symlink': str(p.readlink())}
        elif p.is_file():
            observed[p.relative_to(root).as_posix()] = {'sha256': sha256(p), 'mode': p.stat().st_mode & 0o777}
    assert observed == files, 'Dependency closure inventory mismatch'
    return manifest
