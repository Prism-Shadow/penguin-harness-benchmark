#!/usr/bin/env python3
import argparse
import json
import os
import shutil
from pathlib import Path


def replace_link(target, source):
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def prepare(bundle, repo):
    bundle = bundle.resolve()
    packages = repo / 'packages'
    if not bundle.is_dir() or not packages.is_dir():
        raise ValueError('bundle and workspace packages are required')
    replaced = []
    for current, directories, files in os.walk(bundle, followlinks=False):
        current = Path(current)
        for name in list(directories):
            child = current / name
            if child.is_symlink():
                directories.remove(name)
            elif name in {'.cache', '.npm', '.yarn', '__pycache__'}:
                shutil.rmtree(child)
                directories.remove(name)
            elif name == '@lion':
                directories.remove(name)
                replaced.extend(str(package.relative_to(bundle)) for package in child.iterdir())
                replace_link(child, packages)
        manifest = current / 'package.json'
        if 'package.json' in files:
            payload = json.loads(manifest.read_text())
            name = payload.get('name', '')
            if name.startswith('@lion/'):
                replace_link(current, packages / name.split('/', 1)[1])
                directories.clear()
                replaced.append(str(current.relative_to(bundle)))
    lion = bundle / '@lion'
    replace_link(lion, packages)
    bin_dir = bundle / '.bin'
    if bin_dir.exists():
        shutil.rmtree(bin_dir)
    bin_dir.mkdir()
    roots = []
    for child in sorted(bundle.iterdir()):
        if child.name.startswith('.') or child.name == '@lion':
            continue
        roots.extend(sorted(child.iterdir()) if child.name.startswith('@') else [child])
    for package in roots:
        manifest = package / 'package.json'
        if not manifest.is_file():
            continue
        payload = json.loads(manifest.read_text())
        binaries = payload.get('bin', {})
        if not binaries:
            continue
        if isinstance(binaries, str):
            binaries = {payload['name'].split('/')[-1]: binaries}
        for name, relative in binaries.items():
            source = (package / relative).resolve()
            if Path(name).name != name or not source.is_relative_to(bundle):
                raise ValueError(f'unsafe binary: {manifest}: {name}')
            if not source.is_file():
                raise ValueError(f'missing binary: {source}')
            source.chmod(source.stat().st_mode | 0o111)
            replace_link(bin_dir / name, os.path.relpath(source, bin_dir))
    for name in ['karma', 'eslint', 'prettier']:
        if not (bin_dir / name).is_file() or not (bin_dir / name).is_symlink():
            raise ValueError(f'missing required CLI: {name}')
    return {'workspace': str(repo), 'replaced_lion_sources': replaced, 'bin_count': len(list(bin_dir.iterdir()))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.bundle, args.repo), indent=2))
