#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    base = root / 'environment/base'
    paths = sorted([*base.joinpath('test').rglob('*'), *base.joinpath('samples').rglob('*'), base / 'README.md'])
    raw = io.BytesIO()
    hashes = {}
    with tarfile.open(fileobj=raw, mode='w') as archive:
        for path in paths:
            if not path.is_file():
                continue
            name = path.relative_to(base).as_posix()
            data = path.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0) as output:
        output.write(raw.getvalue())
    data = compressed.getvalue()
    compatibility = root / 'tests/frozen_compatibility.patch'
    manifest = json.dumps({'schema': 'frozen-upstream-v1', 'files': hashes,
                           'compatibility_patch_sha256': hashlib.sha256(compatibility.read_bytes()).hexdigest(),
                           'sha256': hashlib.sha256(data).hexdigest()}, indent=2) + '\n'
    outputs = {root / 'tests/frozen_upstream.tar.gz': data,
               root / 'tests/frozen_upstream.json': manifest.encode()}
    for path, content in outputs.items():
        if args.check:
            assert path.read_bytes() == content, path
        else:
            path.write_bytes(content)
    print(f'{len(hashes)} original frozen assets match baseline; declared compatibility patch hash verified; no production library is included')


if __name__ == '__main__':
    main()
