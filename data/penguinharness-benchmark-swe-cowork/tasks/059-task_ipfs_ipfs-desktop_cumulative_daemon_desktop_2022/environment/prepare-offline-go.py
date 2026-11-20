#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path


CHECKSUM_HOSTS = ('https://dist.ipfs.io', 'https://dist.ipfs.tech')
ATTEMPTS_PER_SOURCE = 2


def checksum(path):
    digest = hashlib.sha512()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(archive, expected):
    if not re.fullmatch(r'[0-9a-f]{128}', expected):
        raise ValueError(f'invalid SHA512: {archive.name}')
    if checksum(archive) != expected:
        raise ValueError(f'SHA512 mismatch: {archive.name}')


def transfer(url, target, resume):
    command = ['curl', '--proto', '=https', '--proto-redir', '=https', '--location',
               '--fail', '--silent', '--show-error', '--connect-timeout', '5',
               '--max-time', '30', '--max-filesize', '67108864', '--output', str(target)]
    if resume:
        command += ['--continue-at', '-']
    completed = subprocess.run(command + [url], capture_output=True, text=True, timeout=35)
    if completed.returncode:
        raise OSError(f'curl exit {completed.returncode}: {completed.stderr.strip()}')


def acquire(urls, target, validate, resume=True):
    partial = target.with_name(target.name + '.partial')
    failures = []
    for url in urls:
        for attempt in range(ATTEMPTS_PER_SOURCE):
            try:
                if resume and partial.is_file():
                    try:
                        validate(partial)
                    except ValueError:
                        pass
                    else:
                        partial.replace(target)
                        return url
                transfer(url, partial, resume and attempt == 0)
                validate(partial)
                partial.replace(target)
                return url
            except ValueError as error:
                partial.unlink(missing_ok=True)
                failures.append(f'{url}: {error}')
            except (OSError, subprocess.TimeoutExpired) as error:
                failures.append(f'{url}: {error}')
            print(f'bounded acquisition attempt {attempt + 1}: {failures[-1]}', flush=True)
    raise RuntimeError('archive preparation failed; verified inputs were preserved; '
                       'rerun --acquire or use --source with the pinned checksum.\n' + '\n'.join(failures))


def parse_checksum(path, filename):
    tokens = path.read_text().strip().split()
    if (len(tokens) not in (1, 2) or not re.fullmatch(r'[0-9a-f]{128}', tokens[0])
            or (len(tokens) == 2 and tokens[1].lstrip('*') != filename)):
        raise ValueError(f'invalid authoritative SHA512 record for {filename}')
    return tokens[0]


def save_lock(path, lock):
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(lock, indent=2) + '\n')
    temporary.replace(path)


def prepare(cache, mirror, baseline_version, lock_path, download=False, source=None):
    lock = json.loads(lock_path.read_text())
    if lock['schema'] != 'stock-go-ipfs-inputs-v1' or lock['platform'] != 'linux-amd64':
        raise ValueError('unsupported stock distribution lock')
    releases = lock['releases']
    versions = [release['version'] for release in releases]
    if len(versions) != len(set(versions)) or baseline_version not in versions:
        raise ValueError('baseline version must be present exactly once in the release lock')
    cache.mkdir(parents=True, exist_ok=True)
    versions_file = mirror / 'go-ipfs/versions'
    versions_file.unlink(missing_ok=True)
    for release in releases:
        version = release['version']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError(f'unsupported go-ipfs version: {version}')
        filename = f'go-ipfs_v{version}_linux-amd64.tar.gz'
        archive = cache / filename
        sidecar = cache / (filename + '.sha512')
        urls = [f'{host}/go-ipfs/v{version}/{filename}' for host in CHECKSUM_HOSTS]
        expected = release.get('sha512')
        if not expected:
            if not download:
                raise FileNotFoundError(f'unprepared authoritative checksum: v{version}; run --acquire before building')
            origin = acquire([url + '.sha512' for url in urls], sidecar,
                             lambda path: parse_checksum(path, filename), resume=False)
            expected = parse_checksum(sidecar, filename)
            release.update(sha512=expected, checksum_source=origin)
            save_lock(lock_path, lock)
        if not re.fullmatch(r'[0-9a-f]{128}', expected):
            raise ValueError(f'invalid pinned SHA512: v{version}')
        if not archive.is_file() and source is not None and (source / filename).is_file():
            local = source / filename
            verify_archive(local, expected)
            temporary = archive.with_name(archive.name + '.partial')
            shutil.copyfile(local, temporary)
            verify_archive(temporary, expected)
            temporary.replace(archive)
        if not archive.is_file():
            if not download:
                raise FileNotFoundError(f'missing pinned archive: {filename}; run --acquire or --source before building')
            urls.append(f'https://github.com/ipfs/kubo/releases/download/v{version}/{filename}')
            acquire(urls, archive, lambda path: verify_archive(path, expected))
        verify_archive(archive, expected)
        sidecar.write_text(f'{expected}  {filename}\n')
        print(f'verified pinned stock archive: v{version} SHA512={expected}', flush=True)
    for version in sorted(versions):
        release_dir = mirror / 'go-ipfs' / f'v{version}'
        release_dir.mkdir(parents=True, exist_ok=True)
        metadata = {'platforms': {'linux': {'archs': {'amd64': {
            'link': f'/go-ipfs_v{version}_linux-amd64.tar.gz'}}}}}
        (release_dir / 'dist.json').write_text(json.dumps(metadata) + '\n')
    versions_file.write_text(''.join(f'v{version}\n' for version in sorted(versions)))
    print('offline distribution complete: ' + ', '.join(sorted(versions)), flush=True)


if __name__ == '__main__':
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise SystemExit('This task requires the linux/amd64 Kubo distribution.')
    parser = argparse.ArgumentParser(description='Verify/import pinned stock Kubo inputs; network requires --acquire.')
    parser.add_argument('--cache', type=Path, default=os.environ.get('NPM_GO_IPFS_CACHE'))
    parser.add_argument('--mirror', type=Path, default=Path('/opt/go-ipfs-dist'))
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('go-ipfs-releases.json'))
    parser.add_argument('--manifest', type=Path, default=Path('package.json'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--acquire', action='store_true')
    arguments = parser.parse_args()
    if arguments.cache is None:
        parser.error('--cache or NPM_GO_IPFS_CACHE is required')
    manifest = json.loads(arguments.manifest.read_text())
    prepare(arguments.cache, arguments.mirror, manifest['dependencies']['go-ipfs'],
            arguments.lock, arguments.acquire, arguments.source)
