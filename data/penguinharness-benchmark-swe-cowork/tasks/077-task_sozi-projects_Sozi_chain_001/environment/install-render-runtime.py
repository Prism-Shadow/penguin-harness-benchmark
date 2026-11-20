import argparse
from collections import deque
from contextlib import contextmanager
import fcntl
import hashlib
import http.client
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


VERSION = '9.2.1'
ARCHIVE = f'electron-v{VERSION}-linux-x64.zip'
RELEASE = f'https://github.com/electron/electron/releases/download/v{VERSION}'
API_RELEASE = f'https://api.github.com/repos/electron/electron/releases/tags/v{VERSION}'
MIRROR_RELEASE = f'https://npmmirror.com/mirrors/electron/v{VERSION}'
SOURCES = ('npmmirror', 'github-release', 'github-api')
MANIFEST = 'SHASUMS256.txt'
PINNED_DIGESTS = {
    ARCHIVE: 'eb0bd52e713594b6a5cdba7815ae55dcb034c05314bc3b4150e45a5466857c79',
    MANIFEST: 'a968425a5277c5cd6baa2ee1fc36d9215078aa1b7b960351d666a4c755712388',
}
MAX_BYTES = {ARCHIVE: 128 * 1024 * 1024, MANIFEST: 1024 * 1024}


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def verified(path, name):
    return path.is_file() and path.stat().st_size <= MAX_BYTES[name] and digest(path) == PINNED_DIGESTS[name]


def expected_digest(manifest):
    matches = re.findall(r'^([0-9a-fA-F]{64})\s+\*?' + re.escape(ARCHIVE) + r'\s*$', manifest, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('release manifest must identify exactly one Linux x64 archive')
    return matches[0].lower()


def install(archive, manifest, destination):
    if not verified(manifest, MANIFEST):
        raise ValueError('Electron release manifest SHA256 mismatch')
    expected = expected_digest(manifest.read_text())
    if expected != PINNED_DIGESTS[ARCHIVE] or not verified(archive, ARCHIVE):
        raise ValueError('Electron archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            relative = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if relative.is_absolute() or '..' in relative.parts or '\\' in entry.filename:
                raise ValueError('unsafe Electron archive path')
            if stat.S_ISLNK(mode):
                raise ValueError('Electron archive symlink not allowed')
        executable = bundle.getinfo('electron')
        if executable.is_dir() or not executable.external_attr >> 16 & stat.S_IXUSR:
            raise ValueError('Electron executable missing or not executable')
        destination.mkdir(parents=True, exist_ok=False)
        bundle.extractall(destination)
        for entry in bundle.infolist():
            target = destination / entry.filename
            target.chmod(0o755 if entry.is_dir() or entry.external_attr >> 16 & 0o111 else 0o644)
    metadata = {
        'electron_version': VERSION, 'archive': ARCHIVE, 'archive_sha256': expected,
        'release': RELEASE, 'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }
    (destination / 'SHASUMS256.txt').write_bytes(manifest.read_bytes())
    (destination / 'runtime-provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


@contextmanager
def time_limit(seconds):
    def expired(signum, frame):
        raise TimeoutError('Electron preparation deadline exceeded')

    previous = signal.signal(signal.SIGALRM, expired)
    started = time.monotonic()
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if previous_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, previous_timer[0] - (time.monotonic() - started)), previous_timer[1])


def asset_url(name, source):
    if name not in PINNED_DIGESTS or source not in SOURCES:
        raise ValueError('unknown pinned Electron asset or source')
    if source == 'npmmirror':
        return MIRROR_RELEASE + '/' + name
    if source == 'github-release':
        return RELEASE + '/' + name
    request = urllib.request.Request(API_RELEASE, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'sozi-runtime-preparation',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError('release metadata too large')
    release = json.loads(payload)
    if release.get('tag_name') != 'v' + VERSION:
        raise ValueError('unexpected Electron release tag')
    matches = [asset for asset in release.get('assets', []) if asset.get('name') == name]
    if len(matches) != 1 or not re.fullmatch(
            r'https://api\.github\.com/repos/electron/electron/releases/assets/[0-9]+', matches[0].get('url', '')):
        raise ValueError('release API must identify exactly one official asset')
    return matches[0]['url']


def transfer(name, partial, source):
    offset = partial.stat().st_size if partial.exists() else 0
    if offset >= MAX_BYTES[name]:
        partial.unlink()
        offset = 0
    headers = {'Accept': 'application/octet-stream', 'Accept-Encoding': 'identity',
               'User-Agent': 'sozi-runtime-preparation'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    request = urllib.request.Request(asset_url(name, source), headers=headers)
    print(f'transfer {name} source={source} resume_bytes={offset}', flush=True)
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status == 206:
            match = re.fullmatch(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)', response.headers.get('Content-Range', ''))
            if not match:
                raise ValueError('invalid resume Content-Range')
            start, end, total = map(int, match.groups())
            if start != offset or not start <= end < total or total > MAX_BYTES[name]:
                raise ValueError('inconsistent resume Content-Range')
            expected = end - start + 1
            mode = 'ab'
        elif response.status == 200:
            if offset:
                print(f'Range ignored by {source}; restarting {name}', flush=True)
            offset = 0
            expected = int(response.headers['Content-Length']) if 'Content-Length' in response.headers else None
            mode = 'wb'
        else:
            raise ValueError(f'unexpected download status: {response.status}')
        if expected is not None and (expected < 0 or offset + expected > MAX_BYTES[name]):
            raise ValueError('release asset exceeds size limit')
        received = 0
        with partial.open(mode) as output:
            read = getattr(response, 'read1', response.read)
            try:
                while True:
                    chunk = read(64 * 1024)
                    if not chunk:
                        break
                    if offset + received + len(chunk) > MAX_BYTES[name]:
                        raise ValueError('release asset exceeds size limit')
                    output.write(chunk)
                    received += len(chunk)
            finally:
                output.flush()
                print(f'transfer {name} source={source} received_bytes={received} retained_bytes={output.tell()}', flush=True)
        if expected is not None and received != expected:
            raise OSError('incomplete Electron response; partial bytes retained')
        if response.status == 206 and end + 1 < total:
            raise OSError('partial Electron range; more bytes required')


def download(name, destination, deadline, attempts):
    if verified(destination, name):
        print(f'verified cache hit: {name}', flush=True)
        return
    partial = destination.with_name(name + '.part')
    if verified(partial, name):
        partial.replace(destination)
        return
    last_error = 'no attempts remaining'
    sources = deque(SOURCES)
    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not sources:
            break
        source = sources.popleft()
        sources.append(source)
        print(f'fetch {name} attempt={attempt + 1}/{attempts} source={source}', flush=True)
        try:
            with time_limit(min(90, remaining)):
                transfer(name, partial, source)
                if not verified(partial, name):
                    partial.unlink(missing_ok=True)
                    raise ValueError('downloaded Electron asset SHA256 mismatch')
                partial.replace(destination)
                return
        except (OSError, ValueError, http.client.HTTPException) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code == 416:
                partial.unlink(missing_ok=True)
            if isinstance(error, urllib.error.HTTPError) and error.code in (404, 410):
                sources.remove(source)
                print(f'unavailable {name} source={source} status={error.code}; skipping this source for this asset', flush=True)
            last_error = f'{type(error).__name__}: {error}'
            print(last_error, file=sys.stderr, flush=True)
        pause = min(2 ** attempt, 8, max(0, deadline - time.monotonic()))
        if sources and attempt + 1 < attempts and pause:
            time.sleep(pause)
    raise RuntimeError(f'bounded Electron preparation failed for {name}: {last_error}; resume with the same cache')


def prepare(cache, timeout=480, attempts=6, seed_assets=None):
    if not math.isfinite(timeout) or not 0 < timeout <= 1800 or not 1 <= attempts <= 12:
        raise ValueError('timeout must be in (0, 1800]; attempts must be in [1, 12]')
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / '.preparation.lock').open('a') as lock, time_limit(timeout):
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deadline = time.monotonic() + timeout
        for name in [MANIFEST, ARCHIVE]:
            if seed_assets is not None and (seed_assets / name).exists():
                if not verified(seed_assets / name, name):
                    raise ValueError(f'seed asset SHA256 mismatch: {name}')
                if not verified(cache / name, name):
                    pending = cache / (name + '.part')
                    shutil.copyfile(seed_assets / name, pending)
                    pending.replace(cache / name)
            download(name, cache / name, deadline, attempts)
    return cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=Path('/opt/verified-electron-9.2.1'))
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--cache', type=Path, default=Path('/opt/sozi-runtime/downloads'))
    parser.add_argument('--seed-assets', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--timeout', type=float, default=480)
    parser.add_argument('--attempts', type=int, default=6)
    arguments = parser.parse_args()
    if arguments.assets:
        if arguments.seed_assets or arguments.prepare_only:
            parser.error('--assets is offline install only; cannot combine with --seed-assets or --prepare-only')
        assets = arguments.assets
    else:
        assets = prepare(arguments.cache, arguments.timeout, arguments.attempts, arguments.seed_assets)
    if arguments.prepare_only:
        print(json.dumps({'verified_assets': str(assets), 'sha256': PINNED_DIGESTS}, sort_keys=True))
        return
    arguments.destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='electron-install-', dir=arguments.destination.parent) as temporary:
        staged = Path(temporary) / 'runtime'
        result = install(assets / ARCHIVE, assets / MANIFEST, staged)
        if arguments.destination.exists():
            raise FileExistsError(arguments.destination)
        staged.rename(arguments.destination)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
