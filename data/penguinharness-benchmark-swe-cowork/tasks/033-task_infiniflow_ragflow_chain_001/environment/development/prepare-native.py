import argparse
import contextlib
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import signal
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_DEADLINE_SECONDS = 900
DOWNLOAD_BLOCK_SIZE = 64 * 1024


def validate_library(library):
    required = {'name', 'version', 'url', 'required'}
    missing = sorted(required - set(library))
    if missing:
        raise ValueError('Native dependency manifest is missing: ' + ', '.join(missing))
    version = str(library['version'])
    parsed = urllib.parse.urlsplit(library['url'])
    if parsed.scheme != 'https' or parsed.hostname != 'github.com' or parsed.username or parsed.password:
        raise ValueError('Native dependency must use an authoritative HTTPS release URL')
    if not version or version not in urllib.parse.unquote(parsed.path):
        raise ValueError('Native dependency URL is not pinned to its manifest version: ' + library['name'])
    expected = library.get('sha256')
    if expected is not None and not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Invalid native dependency sha256: ' + library['name'])
    if 'size' in library and (type(library['size']) is not int or library['size'] <= 0):
        raise ValueError('Invalid native dependency size: ' + library['name'])


@contextlib.contextmanager
def bounded_transfer(seconds):
    def expired(signum, frame):
        raise TimeoutError('native archive download deadline exceeded')

    previous_handler = signal.signal(signal.SIGALRM, expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def _release_asset_matches(asset_url, prefix, tag, filename):
    if not isinstance(asset_url, str):
        return False
    try:
        parsed = urllib.parse.urlsplit(asset_url)
    except ValueError:
        return False
    if (parsed.scheme, parsed.netloc, parsed.query, parsed.fragment) != ('https', 'github.com', '', ''):
        return False
    if not parsed.path.startswith(prefix):
        return False
    asset_tag, separator, asset_name = parsed.path[len(prefix):].rpartition('/')
    return bool(separator) and asset_name == filename and urllib.parse.unquote(asset_tag) == tag


def resolve_library(library, opener=urllib.request.urlopen):
    validate_library(library)
    if library.get('sha256'):
        return library
    parsed = urllib.parse.urlsplit(library['url'])
    parts = parsed.path.strip('/').split('/')
    if len(parts) != 6 or parts[2:4] != ['releases', 'download']:
        raise ValueError('Invalid authoritative native release URL')
    tag = urllib.parse.unquote(parts[4])
    metadata_url = f'https://api.github.com/repos/{parts[0]}/{parts[1]}/releases/tags/{urllib.parse.quote(tag, safe="")}'
    request = urllib.request.Request(metadata_url, headers={'Accept': 'application/vnd.github+json'})
    with bounded_transfer(30), opener(request, timeout=30) as response:
        metadata = json.loads(response.read(1024 * 1024 + 1))
    if metadata.get('tag_name') != tag:
        raise RuntimeError('Native release metadata tag mismatch: ' + library['name'])
    prefix = '/' + '/'.join(parts[:4]) + '/'
    matches = [asset for asset in metadata.get('assets', [])
               if _release_asset_matches(asset.get('browser_download_url'), prefix, tag, parts[5])]
    if len(matches) != 1:
        published = [asset.get('browser_download_url') for asset in metadata.get('assets', [])]
        raise RuntimeError(f"Missing or duplicate native release asset: {library['name']}; "
                           f"expected {library['url']!r}; published URLs: {published[:10]!r}")
    asset = matches[0]
    digest = asset.get('digest') or ''
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise RuntimeError('Authoritative native SHA256 unavailable; supply an independently verified pinned manifest')
    asset_url = asset.get('url') or ''
    if not re.fullmatch(re.escape(f'https://api.github.com/repos/{parts[0]}/{parts[1]}/releases/assets/') + r'[0-9]+', asset_url):
        raise RuntimeError('Invalid authoritative native asset URL')
    if type(asset.get('size')) is not int or asset['size'] <= 0:
        raise RuntimeError('Invalid authoritative native asset size')
    print(f"Verified release metadata: {library['name']} {library['version']} sha256={digest[7:]}", flush=True)
    return dict(library, sha256=digest[7:], size=asset['size'], metadata_url=metadata_url,
                asset_url=asset_url)


def archive_name(library):
    validate_library(library)
    name = library['name'] + '-' + library['version']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
        raise ValueError('Unsafe native archive name')
    return name + '.tar.gz'


def _request(opener, library, offset, timeout, alternate=False):
    headers = {'Range': f'bytes={offset}-'} if offset else {}
    url = library['url']
    if alternate and library.get('asset_url'):
        url = library['asset_url']
        headers['Accept'] = 'application/octet-stream'
    request = urllib.request.Request(url, headers=headers)
    return opener(request, timeout=timeout)


def _response_status(response):
    return getattr(response, 'status', None) or getattr(response, 'code', None) or 200


def _content_range(response):
    headers = getattr(response, 'headers', {})
    value = headers.get('Content-Range') if headers is not None else None
    if not value:
        return None
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)', value.strip())
    if not match:
        raise RuntimeError('Invalid native archive Content-Range')
    return tuple(None if item == '*' else int(item) for item in match.groups())


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(DOWNLOAD_BLOCK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def _verify_download(library, archive_path, declared_size=None):
    size = archive_path.stat().st_size
    if library.get('size') is not None and size != library['size']:
        raise http.client.IncompleteRead(b'', library['size'] - size)
    if declared_size is not None and size != declared_size:
        raise http.client.IncompleteRead(b'', declared_size - size)
    digest = _hash_file(archive_path)
    expected = library['sha256']
    if digest != expected:
        raise RuntimeError('Native archive checksum mismatch: ' + library['name'])
    return dict(library, sha256=digest, size=size)


def download_archive(library, archive_path, opener=urllib.request.urlopen, sleeper=time.sleep,
                     timeout=DOWNLOAD_TIMEOUT_SECONDS, deadline=DOWNLOAD_DEADLINE_SECONDS):
    validate_library(library)
    if not library.get('sha256'):
        raise RuntimeError('Native download requires an authoritative pinned SHA256')
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = archive_path.with_name(archive_path.name + '.part')
    state_path = partial_path.with_name(partial_path.name + '.json')
    for path in (archive_path, partial_path, state_path):
        if path.is_symlink():
            raise RuntimeError('Native download cache cannot contain symlinks')
    identity = {key: library[key] for key in ('name', 'version', 'url', 'sha256')}
    if partial_path.exists() and (not state_path.exists() or json.loads(state_path.read_text()) != identity):
        raise RuntimeError('Native partial cache does not match dependency manifest')
    state_path.write_text(json.dumps(identity))
    started = time.monotonic()
    last_error = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        remaining = deadline - (time.monotonic() - started)
        if remaining <= 0:
            break
        offset = partial_path.stat().st_size if partial_path.exists() else 0
        if library.get('size') is not None and offset > library['size']:
            partial_path.unlink()
            offset = 0
        if offset and offset == library.get('size'):
            try:
                record = _verify_download(library, partial_path)
            except RuntimeError:
                partial_path.unlink()
                offset = 0
            else:
                partial_path.replace(archive_path)
                state_path.unlink(missing_ok=True)
                return record
        attempt_budget = remaining / (DOWNLOAD_ATTEMPTS - attempt + 1)
        alternate = attempt % 2 == 0 and bool(library.get('asset_url'))
        route = 'api-asset' if alternate else 'release'
        print(f"Downloading {library['name']} {library['version']} "
              f"(attempt {attempt}/{DOWNLOAD_ATTEMPTS}, offset {offset}, route={route}, "
              f"request_budget={attempt_budget:.2f}s, remaining={remaining:.2f}s)", flush=True)
        try:
            request_timeout = min(timeout, attempt_budget)
            with bounded_transfer(attempt_budget), _request(opener, library, offset, request_timeout,
                                                            alternate=alternate) as response:
                status = _response_status(response)
                range_info = _content_range(response)
                if offset and status == 206:
                    if range_info is None or range_info[0] != offset:
                        raise RuntimeError('Native archive resume offset mismatch: ' + library['name'])
                    mode = 'ab'
                else:
                    if offset and status not in (200, 206):
                        raise RuntimeError('Native archive download returned unexpected status')
                    mode = 'wb'
                    offset = 0
                headers = getattr(response, 'headers', {})
                content_length = headers.get('Content-Length') if headers is not None else None
                declared_size = None
                if range_info is not None and range_info[2] is not None:
                    declared_size = range_info[2]
                elif content_length is not None:
                    declared_size = offset + int(content_length)
                with partial_path.open(mode) as output:
                    read = getattr(response, 'read1', response.read)
                    received = offset
                    while block := read(DOWNLOAD_BLOCK_SIZE):
                        received += len(block)
                        if library.get('size') is not None and received > library['size']:
                            raise RuntimeError('Native archive exceeds authoritative size: ' + library['name'])
                        output.write(block)
                        remaining = deadline - (time.monotonic() - started)
                        if remaining <= 0:
                            raise TimeoutError('native archive download deadline exceeded')
            record = _verify_download(library, partial_path, declared_size)
            partial_path.replace(archive_path)
            state_path.unlink(missing_ok=True)
            return record
        except (OSError, urllib.error.URLError, http.client.IncompleteRead) as error:
            last_error = error
            retryable = (not isinstance(error, urllib.error.HTTPError)
                         or error.code in (408, 429, 500, 502, 503, 504)
                         or bool(library.get('asset_url')))
            print(f"Download failed for {library['name']}: {error}", flush=True)
            if not retryable:
                break
        except (RuntimeError, TimeoutError) as error:
            last_error = error
            print(f"Download failed for {library['name']}: {error}", flush=True)
            partial_path.unlink(missing_ok=True)
        retained = partial_path.stat().st_size if partial_path.exists() else 0
        print(f"Native retry state: {library['name']} route={route} retained_bytes={retained}", flush=True)
        remaining = deadline - (time.monotonic() - started)
        if attempt < DOWNLOAD_ATTEMPTS and remaining > 0:
            sleeper(min(attempt, remaining / (DOWNLOAD_ATTEMPTS - attempt + 1)))
    raise RuntimeError(
        f"Native download failed: {library['name']} {library['url']}; "
        'provide a verified --archive-directory bundle or restore build-network access'
    ) from last_error


def cached_archive(library, directory):
    directory = Path(directory)
    if directory.is_symlink() or (directory / 'receipt.json').is_symlink():
        raise RuntimeError('Native bundle cannot contain symlinked metadata')
    records = json.loads((directory / 'receipt.json').read_text())
    matches = [record for record in records if record.get('name') == library['name']]
    if len(matches) != 1:
        raise RuntimeError('Missing or duplicate native bundle record: ' + library['name'])
    record = matches[0]
    validate_library(library)
    if not library.get('sha256'):
        raise RuntimeError('Native cache verification requires an authoritative pinned SHA256')
    if any(record.get(key) != value for key, value in library.items()):
        raise RuntimeError('Native bundle does not match dependency manifest: ' + library['name'])
    archive = directory / archive_name(library)
    if archive.is_symlink() or not archive.is_file():
        raise RuntimeError('Missing regular native archive: ' + str(archive))
    if _hash_file(archive) != record.get('sha256') or archive.stat().st_size != record.get('size'):
        raise RuntimeError('Native archive checksum/size mismatch: ' + library['name'])
    if library.get('sha256') and record.get('sha256') != library['sha256']:
        raise RuntimeError('Native archive checksum does not match manifest: ' + library['name'])
    return archive, record


def _cache_record_path(library, directory):
    return Path(directory) / (archive_name(library) + '.json')


def cached_partial_archive(library, directory):
    directory = Path(directory)
    record_path = _cache_record_path(library, directory)
    archive = directory / archive_name(library)
    if directory.is_symlink() or record_path.is_symlink():
        raise RuntimeError('Native cache cannot contain symlinked metadata')
    if not record_path.exists() and not archive.exists():
        return None
    if not library.get('sha256'):
        raise RuntimeError('Native cache verification requires an authoritative pinned SHA256')
    if archive.is_file() and not archive.is_symlink() and not record_path.exists():
        record = _verify_download(library, archive)
        _write_cache_record(library, directory, record)
        return archive, record
    if not record_path.is_file() or not archive.is_file() or archive.is_symlink():
        raise RuntimeError('Incomplete native cache entry: ' + library['name'])
    record = json.loads(record_path.read_text())
    if any(record.get(key) != value for key, value in library.items()):
        raise RuntimeError('Native cache does not match dependency manifest: ' + library['name'])
    if _hash_file(archive) != record.get('sha256') or archive.stat().st_size != record.get('size'):
        raise RuntimeError('Native cache checksum/size mismatch: ' + library['name'])
    if library.get('sha256') and record.get('sha256') != library['sha256']:
        raise RuntimeError('Native cache checksum does not match manifest: ' + library['name'])
    return archive, record


def _write_cache_record(library, directory, record):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = _cache_record_path(library, directory)
    temporary = target.with_name(target.name + '.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(target)


def extract_library(library, archive_path, destination):
    with tarfile.open(archive_path) as archive:
        archive.extractall(destination, filter='data')
    for relative in library['required']:
        path = destination / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing native dependency: {library['name']}/{relative}")


def install_library(library, destination, temporary_root, opener=urllib.request.urlopen,
                    sleeper=time.sleep, archive_directory=None, offline=False, cache_directory=None):
    destination = Path(destination)
    with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
        temporary = Path(temporary)
        if archive_directory is not None and (Path(archive_directory) / 'receipt.json').exists():
            archive_path, record = cached_archive(library, archive_directory)
            print(f"Verified local native archive: {library['name']} sha256={record['sha256']}", flush=True)
        elif cache_directory is not None and (cached := cached_partial_archive(library, cache_directory)) is not None:
            archive_path, record = cached
            print(f"Verified cached native archive: {library['name']} sha256={record['sha256']}", flush=True)
        else:
            if offline:
                raise RuntimeError('Offline native bundle receipt is missing; provide --archive-directory or a verified cache')
            archive_path = (Path(cache_directory) / archive_name(library)
                            if cache_directory is not None else temporary / 'library.tar.gz')
            record = download_archive(library, archive_path, opener, sleeper)
            if cache_directory is not None:
                _write_cache_record(library, cache_directory, record)
        extracted = temporary / 'extracted'
        extracted.mkdir()
        extract_library(library, archive_path, extracted)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise RuntimeError('Native installation destination cannot be a symlink')
        if destination.exists():
            shutil.rmtree(destination)
        extracted.replace(destination)
    return record


def export_bundle(libraries, directory, temporary_root, opener=urllib.request.urlopen, sleeper=time.sleep):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for library in libraries:
        cached = cached_partial_archive(library, directory)
        if cached is not None:
            archive, record = cached
        else:
            archive = directory / archive_name(library)
            record = download_archive(library, archive, opener, sleeper)
        with tempfile.TemporaryDirectory(dir=temporary_root) as extracted:
            extract_library(library, archive, Path(extracted))
        _write_cache_record(library, directory, record)
        records.append(record)
    receipt = directory / 'receipt.json'
    temporary = receipt.with_name('receipt.json.tmp')
    temporary.write_text(json.dumps(records, indent=2) + '\n')
    temporary.replace(receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('native-libraries.json'))
    parser.add_argument('--destination', type=Path, default=Path('/opt/ragflow-native-libs'))
    parser.add_argument('--temporary-root', type=Path, default=Path('/tmp'))
    parser.add_argument('--archive-directory', type=Path, default=Path(__file__).with_name('native-archives'))
    parser.add_argument('--cache-directory', type=Path,
                        default=Path(os.environ.get('RAGFLOW_NATIVE_CACHE_DIRECTORY',
                                                    '/opt/ragflow-native-cache')))
    parser.add_argument('--download-only', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    bundle_manifest = args.archive_directory / 'manifest.json'
    if bundle_manifest.exists():
        if bundle_manifest.is_symlink():
            raise RuntimeError('Native bundle manifest cannot be a symlink')
        pinned_manifest = json.loads(bundle_manifest.read_text())
        if pinned_manifest.get('architecture') != manifest['architecture']:
            raise RuntimeError('Native bundle architecture mismatch')
        pinned_libraries = pinned_manifest.get('libraries', [])
        if len(pinned_libraries) != len(manifest['libraries']):
            raise RuntimeError('Native bundle dependency count mismatch')
        for library, pinned in zip(manifest['libraries'], pinned_libraries, strict=True):
            if any(pinned.get(key) != value for key, value in library.items()) or not pinned.get('sha256'):
                raise RuntimeError('Native bundle manifest dependency mismatch')
            validate_library(pinned)
        manifest = pinned_manifest
    if platform.machine() != manifest['architecture']:
        raise RuntimeError('Native dependency bundle requires ' + manifest['architecture'])
    for index, library in enumerate(manifest['libraries']):
        if not library.get('sha256'):
            metadata_path = _cache_record_path(library, args.cache_directory).with_suffix('.metadata.json')
            if metadata_path.is_symlink():
                raise RuntimeError('Native metadata cache cannot be a symlink')
            if metadata_path.exists():
                pinned = json.loads(metadata_path.read_text())
                if any(pinned.get(key) != value for key, value in library.items()) or not pinned.get('sha256'):
                    raise RuntimeError('Native metadata cache does not match manifest')
                validate_library(pinned)
            elif args.offline:
                raise RuntimeError('Offline native bundle receipt is missing a pinned manifest or cached authoritative metadata')
            else:
                pinned = resolve_library(library)
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                metadata_path.write_text(json.dumps(pinned, indent=2) + '\n')
            manifest['libraries'][index] = pinned
    if args.download_only:
        if args.offline:
            parser.error('--download-only cannot be combined with --offline')
        export_bundle(manifest['libraries'], args.archive_directory, args.temporary_root)
        (args.archive_directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return
    records = [install_library(library, args.destination / library['name'], args.temporary_root,
                               archive_directory=args.archive_directory, offline=args.offline,
                               cache_directory=args.cache_directory)
               for library in manifest['libraries']]
    (args.destination / 'receipt.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
