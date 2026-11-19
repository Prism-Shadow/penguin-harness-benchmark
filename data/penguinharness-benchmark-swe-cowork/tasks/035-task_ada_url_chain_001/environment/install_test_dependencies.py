#!/usr/bin/env python3
"""Stage fixed upstream test versions; enforce any supplied integrity pins."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--googletest-sha256', default='')
    parser.add_argument('--simdjson-sha256', default='')
    parser.add_argument('--root', type=Path, default=Path('/opt/ada-test-deps'))
    args = parser.parse_args()
    packages = [
        ('googletest', '1.15.2', 'google/googletest', args.googletest_sha256),
        ('simdjson', '3.10.1', 'simdjson/simdjson', args.simdjson_sha256),
    ]
    for name, version, repository, digest in packages:
        if digest and not re.fullmatch('[0-9a-f]{64}', digest):
            parser.error(f'{name} SHA256 must be 64 lowercase hexadecimal characters')
    args.root.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, version, repository, digest in packages:
        url = f'https://codeload.github.com/{repository}/tar.gz/refs/tags/v{version}'
        archive = args.root / f'{name}.tar.gz'
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest and actual != digest:
            raise ValueError(f'{name} SHA256 mismatch: {actual}')
        with tarfile.open(archive) as bundle:
            prefix = f'{name}-{version}'
            for member in bundle.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != prefix:
                    raise ValueError(f'unsafe archive path: {member.name}')
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f'unsupported archive entry: {member.name}')
            bundle.extractall(args.root)
        (args.root / prefix).rename(args.root / name)
        archive.unlink()
        manifest.append({'name': name, 'version': version, 'url': url,
                         'sha256': actual, 'expected_sha256': digest or None,
                         'integrity': 'checksum-verified' if digest else 'version-pinned-tls'})
    (args.root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
