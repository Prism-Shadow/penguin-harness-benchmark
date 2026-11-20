import hashlib
import gzip
import http.client
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
import time
import urllib.error
from pathlib import Path

import pytest


ENVIRONMENT = Path(__file__).resolve().parents[2] / 'environment'
SPEC = importlib.util.spec_from_file_location('prepare_native', ENVIRONMENT / 'development/prepare-native.py')
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)
DECLARED_MANIFEST = json.loads((ENVIRONMENT / 'development/native-libraries.json').read_text())


def archive_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return gzip.compress(output.getvalue(), mtime=0)


def pin_fixture(library, raw):
    return dict(library, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))


MANIFEST = dict(DECLARED_MANIFEST, libraries=[
    pin_fixture(library, archive_bytes({name: name.encode() for name in library['required']}))
    for library in DECLARED_MANIFEST['libraries']
])


def request_url(request):
    return request.full_url if hasattr(request, 'full_url') else request


@pytest.mark.parametrize('library', MANIFEST['libraries'], ids=lambda library: library['name'])
def test_install_native_archive_and_record_digest(tmp_path, library):
    files = {name: ('fixture:' + name).encode() for name in library['required']}
    raw = archive_bytes(files)
    library = pin_fixture(library, raw)

    def open_archive(request, timeout):
        assert request_url(request) == library['url']
        assert timeout <= PREPARE.DOWNLOAD_TIMEOUT_SECONDS
        return io.BytesIO(raw)

    destination = tmp_path / 'installed'
    result = PREPARE.install_library(library, destination, tmp_path, opener=open_archive)
    assert result['sha256'] == hashlib.sha256(raw).hexdigest()
    for name, content in files.items():
        assert (destination / name).read_bytes() == content
    assert sorted(path.name for path in tmp_path.iterdir()) == ['installed']


@pytest.mark.parametrize('files', [{}, {'lib/liboffice_oxide.a': b''}])
def test_missing_or_empty_native_library_fails(tmp_path, files):
    raw = archive_bytes(files)
    with pytest.raises(RuntimeError, match='Missing native dependency'):
        PREPARE.install_library(pin_fixture(MANIFEST['libraries'][0], raw), tmp_path / 'installed', tmp_path,
                                opener=lambda *args, **kwargs: io.BytesIO(raw))


def test_native_archive_cannot_escape_destination(tmp_path):
    raw = archive_bytes({'../escaped': b'not allowed'})
    with pytest.raises(tarfile.FilterError):
        PREPARE.install_library(pin_fixture(MANIFEST['libraries'][0], raw), tmp_path / 'installed', tmp_path,
                                opener=lambda *args, **kwargs: io.BytesIO(raw))
    assert not (tmp_path / 'escaped').exists()


def test_native_download_failure_is_not_accepted(tmp_path):
    def unavailable(*args, **kwargs):
        raise OSError('download unavailable')

    with pytest.raises(RuntimeError, match='Native download failed') as failure:
        PREPARE.install_library(MANIFEST['libraries'][0], tmp_path / 'installed', tmp_path,
                                opener=unavailable, sleeper=lambda delay: None)
    assert str(failure.value.__cause__) == 'download unavailable'
    assert not (tmp_path / 'installed').exists()


def test_transient_connection_and_partial_stream_retry_from_zero(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    calls = []
    delays = []

    class BrokenStream(io.BytesIO):
        def read(self, size):
            if self.tell():
                raise http.client.IncompleteRead(b'partial')
            return super().read(7)

        read1 = read

    def flaky(request, timeout):
        calls.append((request_url(request), timeout, dict(request.header_items())))
        if len(calls) == 1:
            raise urllib.error.URLError(TimeoutError('connection timed out'))
        if len(calls) == 2:
            return BrokenStream(raw)
        return io.BytesIO(raw)

    result = PREPARE.install_library(library, tmp_path / 'installed', tmp_path,
                                     opener=flaky, sleeper=delays.append)
    assert [call[:2] for call in calls] == [
        (library['url'], PREPARE.DOWNLOAD_TIMEOUT_SECONDS),
    ] * 3
    assert delays == [1, 2]
    assert result['sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['size'] == len(raw)
    for name in library['required']:
        assert (tmp_path / 'installed' / name).read_bytes() == name.encode()


@pytest.mark.parametrize('status, attempts', [(404, 1), (403, 1), (429, 3), (503, 3)])
def test_http_failures_are_bounded_and_identify_dependency(tmp_path, status, attempts):
    library = MANIFEST['libraries'][0]
    calls = []
    delays = []

    def unavailable(request, timeout):
        url = request_url(request)
        calls.append(url)
        raise urllib.error.HTTPError(url, status, 'unavailable', {}, None)

    with pytest.raises(RuntimeError, match='office_oxide.*provide a verified'):
        PREPARE.install_library(library, tmp_path / 'installed', tmp_path,
                                opener=unavailable, sleeper=delays.append)
    assert calls == [library['url']] * attempts
    assert delays == list(range(1, attempts))
    assert not list(tmp_path.iterdir())


def test_content_length_mismatch_never_publishes_installation(tmp_path):
    class ShortStream(io.BytesIO):
        headers = {'Content-Length': '800'}

    calls = []

    def truncated(request, timeout):
        calls.append(request_url(request))
        return ShortStream(b'only a prefix')

    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.install_library(MANIFEST['libraries'][0], tmp_path / 'installed', tmp_path,
                                opener=truncated, sleeper=lambda delay: None)
    assert len(calls) == 3
    assert not list(tmp_path.iterdir())


def make_bundle(tmp_path):
    bundle = tmp_path / 'bundle'

    def download(request, timeout):
        url = request_url(request)
        library = next(library for library in MANIFEST['libraries'] if library['url'] == url)
        return io.BytesIO(archive_bytes({name: name.encode() for name in library['required']}))

    PREPARE.export_bundle(MANIFEST['libraries'], bundle, tmp_path, opener=download)
    return bundle


def no_network(*args, **kwargs):
    pytest.fail('An offline or invalid bundle must not access the network')


def test_frozen_bundle_roundtrip_is_offline_and_checks_all_libraries(tmp_path):
    bundle = make_bundle(tmp_path)
    expected = json.loads((bundle / 'receipt.json').read_text())
    records = []
    for library in MANIFEST['libraries']:
        destination = tmp_path / 'installed' / library['name']
        records.append(PREPARE.install_library(library, destination, tmp_path, opener=no_network,
                                               archive_directory=bundle, offline=True))
        for name in library['required']:
            assert (destination / name).read_bytes() == name.encode()
    assert records == expected


@pytest.mark.parametrize('change', ['archive', 'digest', 'size', 'version', 'url', 'missing', 'duplicate', 'symlink'])
def test_invalid_bundle_fails_closed_without_network(tmp_path, change):
    bundle = make_bundle(tmp_path)
    receipt_path = bundle / 'receipt.json'
    records = json.loads(receipt_path.read_text())
    archive = bundle / PREPARE.archive_name(MANIFEST['libraries'][0])
    if change == 'archive':
        archive.write_bytes(archive.read_bytes() + b'tampered')
    elif change == 'digest':
        records[0]['sha256'] = '0' * 64
    elif change == 'size':
        records[0]['size'] += 1
    elif change in ('version', 'url'):
        records[0][change] = 'another-release'
    elif change == 'missing':
        records.pop(0)
    elif change == 'duplicate':
        records.append(records[0])
    else:
        target = tmp_path / 'linked-archive'
        archive.rename(target)
        archive.symlink_to(target)
    receipt_path.write_text(json.dumps(records))
    with pytest.raises(RuntimeError):
        PREPARE.install_library(MANIFEST['libraries'][0], tmp_path / 'installed', tmp_path,
                                opener=no_network, archive_directory=bundle)
    assert not (tmp_path / 'installed').exists()


def test_offline_without_bundle_never_falls_back_to_download(tmp_path):
    with pytest.raises(RuntimeError, match='Offline native bundle receipt is missing'):
        PREPARE.install_library(MANIFEST['libraries'][0], tmp_path / 'installed', tmp_path,
                                opener=no_network, archive_directory=tmp_path / 'absent', offline=True)
    assert not list(tmp_path.iterdir())


def test_existing_files_cannot_mask_incomplete_new_archive(tmp_path):
    library = MANIFEST['libraries'][0]
    destination = tmp_path / 'installed'
    for relative in library['required']:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'old installation')
    with pytest.raises(RuntimeError, match='Missing native dependency'):
        PREPARE.install_library(pin_fixture(library, archive_bytes({})), destination, tmp_path,
                                opener=lambda *args, **kwargs: io.BytesIO(archive_bytes({})))
    for relative in library['required']:
        assert (destination / relative).read_bytes() == b'old installation'


def test_failed_bundle_export_does_not_publish_receipt(tmp_path):
    with pytest.raises(RuntimeError, match='Missing native dependency'):
        PREPARE.export_bundle([pin_fixture(library, archive_bytes({})) for library in MANIFEST['libraries']], tmp_path / 'bundle', tmp_path,
                              opener=lambda *args, **kwargs: io.BytesIO(archive_bytes({})))
    assert not (tmp_path / 'bundle/receipt.json').exists()


def test_offline_cli_installs_bundle_and_writes_receipt(tmp_path):
    bundle = make_bundle(tmp_path)
    (bundle / 'manifest.json').write_text(json.dumps(MANIFEST))
    destination = tmp_path / 'installed'
    result = subprocess.run([
        sys.executable, str(ENVIRONMENT / 'development/prepare-native.py'), '--offline',
        '--archive-directory', str(bundle), '--destination', str(destination),
        '--temporary-root', str(tmp_path),
        '--cache-directory', str(tmp_path / 'cache'),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (destination / 'receipt.json').read_bytes() == (bundle / 'receipt.json').read_bytes()
    assert result.stdout.count('Verified local native archive:') == 3


def test_offline_cli_missing_bundle_does_not_publish_receipt(tmp_path):
    destination = tmp_path / 'installed'
    result = subprocess.run([
        sys.executable, str(ENVIRONMENT / 'development/prepare-native.py'), '--offline',
        '--archive-directory', str(tmp_path / 'absent'), '--destination', str(destination),
        '--temporary-root', str(tmp_path),
        '--cache-directory', str(tmp_path / 'cache'),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Offline native bundle receipt is missing' in result.stderr
    assert not destination.exists()


def test_dependency_versions_match_real_baseline_build_contract():
    script = (ENVIRONMENT / 'base/build.sh').read_text()
    module = (ENVIRONMENT / 'base/go.mod').read_text()
    keys = {'office_oxide': 'OFFICE_OXIDE_VERSION', 'pdfium-static': 'PDFIUM_STATIC_VERSION',
            'pdf_oxide': 'PDF_OXIDE_VERSION'}
    for library in MANIFEST['libraries']:
        version = re.search(r'^' + keys[library['name']] + r'="([^"]+)"$', script, re.M).group(1)
        assert library['version'] == version
        if library['name'] != 'pdfium-static':
            assert 'github.com/yfedoseev/' + library['name'] + '/go v' + version in module


def seed_partial(library, directory, prefix):
    archive = directory / PREPARE.archive_name(library)
    partial = archive.with_name(archive.name + '.part')
    partial.write_bytes(prefix)
    partial.with_name(partial.name + '.json').write_text(json.dumps({
        key: library[key] for key in ('name', 'version', 'url', 'sha256')
    }))
    return archive, partial


def test_resume_persisted_partial_uses_validated_range_and_exact_digest(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive, partial = seed_partial(library, tmp_path, raw[:23])

    class RangedStream(io.BytesIO):
        status = 206
        headers = {'Content-Range': f'bytes 23-{len(raw) - 1}/{len(raw)}',
                   'Content-Length': str(len(raw) - 23)}

    def resume(request, timeout):
        assert request.get_header('Range') == 'bytes=23-'
        return RangedStream(raw[23:])

    record = PREPARE.download_archive(library, archive, opener=resume)
    assert archive.read_bytes() == raw
    assert record['sha256'] == library['sha256']
    assert not partial.exists()


def test_ignored_range_restarts_without_concatenating_old_prefix(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive, partial = seed_partial(library, tmp_path, raw[:17])
    PREPARE.download_archive(library, archive, opener=lambda *args, **kwargs: io.BytesIO(raw))
    assert archive.read_bytes() == raw
    assert not partial.exists()


def test_bad_resume_offset_rejected_then_restarted(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive, partial = seed_partial(library, tmp_path, raw[:19])
    calls = []

    class WrongRange(io.BytesIO):
        status = 206
        headers = {'Content-Range': f'bytes 20-{len(raw) - 1}/{len(raw)}'}

    def respond(request, timeout):
        calls.append(request.get_header('Range'))
        return WrongRange(raw[20:]) if len(calls) == 1 else io.BytesIO(raw)

    PREPARE.download_archive(library, archive, opener=respond, sleeper=lambda delay: None)
    assert calls == ['bytes=19-', None]
    assert archive.read_bytes() == raw


def test_checksum_mismatch_never_publishes_download_or_install(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    wrong = raw[:-1] + bytes([raw[-1] ^ 1])
    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.install_library(library, tmp_path / 'installed', tmp_path,
                                opener=lambda *args, **kwargs: io.BytesIO(wrong),
                                sleeper=lambda delay: None, cache_directory=tmp_path / 'cache')
    assert not (tmp_path / 'installed').exists()
    assert not (tmp_path / 'cache' / PREPARE.archive_name(library)).exists()


def test_trickling_read_cannot_exceed_total_deadline(tmp_path):
    library = MANIFEST['libraries'][0]
    archive = tmp_path / PREPARE.archive_name(library)

    class SlowStream(io.BytesIO):
        def read1(self, size):
            time.sleep(2)
            return super().read(1)

    started = time.monotonic()
    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.download_archive(library, archive, deadline=0.05,
                                 opener=lambda *args, **kwargs: SlowStream(b'trickle'))
    assert time.monotonic() - started < 1
    assert not archive.exists()


def test_failed_download_preserves_prefix_across_invocations(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive = tmp_path / PREPARE.archive_name(library)

    class BrokenStream(io.BytesIO):
        def read1(self, size):
            if self.tell():
                raise TimeoutError('connection interrupted')
            return super().read(11)

    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.download_archive(library, archive,
                                 opener=lambda *args, **kwargs: BrokenStream(raw),
                                 sleeper=lambda delay: None)
    assert archive.with_name(archive.name + '.part').read_bytes() == raw[:11]
    PREPARE.download_archive(library, archive, opener=lambda *args, **kwargs: io.BytesIO(raw))
    assert archive.read_bytes() == raw


def test_request_deadline_reserves_authoritative_fallback(tmp_path):
    library = dict(MANIFEST['libraries'][0],
                   asset_url='https://api.github.com/repos/yfedoseev/office_oxide/releases/assets/42')
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive = tmp_path / PREPARE.archive_name(library)
    calls = []

    class StalledRelease(io.BytesIO):
        def read1(self, size):
            if self.tell():
                time.sleep(2)
            return super().read(11)

    class ResumedAsset(io.BytesIO):
        status = 206
        headers = {'Content-Range': f'bytes 11-{len(raw) - 1}/{len(raw)}',
                   'Content-Length': str(len(raw) - 11)}

    def respond(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            return StalledRelease(raw)
        assert request.full_url == library['asset_url']
        assert request.get_header('Accept') == 'application/octet-stream'
        assert request.get_header('Range') == 'bytes=11-'
        return ResumedAsset(raw[11:])

    started = time.monotonic()
    record = PREPARE.download_archive(library, archive, opener=respond,
                                     sleeper=lambda delay: None, deadline=0.3)
    assert time.monotonic() - started < 1
    assert calls == [library['url'], library['asset_url']]
    assert record['sha256'] == library['sha256']
    assert archive.read_bytes() == raw
    assert not archive.with_name(archive.name + '.part').exists()


def test_failed_authoritative_alternate_returns_to_release(tmp_path):
    library = dict(MANIFEST['libraries'][0],
                   asset_url='https://api.github.com/repos/yfedoseev/office_oxide/releases/assets/42')
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive = tmp_path / PREPARE.archive_name(library)
    calls = []

    def respond(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 503, 'temporary failure', {}, None)
        if request.full_url == library['asset_url']:
            raise urllib.error.URLError('API asset endpoint unavailable')
        return io.BytesIO(raw)

    record = PREPARE.download_archive(library, archive, opener=respond,
                                     sleeper=lambda delay: None)
    assert calls == [library['url'], library['asset_url'], library['url']]
    assert record['sha256'] == library['sha256']
    assert archive.read_bytes() == raw


def test_all_stalled_requests_remain_bounded_and_preserve_progress(tmp_path, capsys):
    library = dict(MANIFEST['libraries'][0],
                   asset_url='https://api.github.com/repos/yfedoseev/office_oxide/releases/assets/42')
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive = tmp_path / PREPARE.archive_name(library)
    calls = []

    class StalledRange(io.BytesIO):
        status = 206

        def __init__(self, offset):
            super().__init__(raw[offset:])
            self.headers = {'Content-Range': f'bytes {offset}-{len(raw) - 1}/{len(raw)}'}

        def read1(self, size):
            if self.tell():
                time.sleep(2)
            return super().read(7)

    def respond(request, timeout):
        offset = int(request.get_header('Range', 'bytes=0-')[6:-1])
        calls.append((request.full_url, offset))
        return StalledRange(offset)

    started = time.monotonic()
    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.download_archive(library, archive, opener=respond,
                                 sleeper=lambda delay: None, deadline=0.3)
    assert time.monotonic() - started < 1
    assert calls == [(library['url'], 0), (library['asset_url'], 7), (library['url'], 14)]
    assert not archive.exists()
    assert archive.with_name(archive.name + '.part').read_bytes() == raw[:21]
    log = capsys.readouterr().out
    assert 'retained_bytes=21' in log and 'route=api-asset' in log
    PREPARE.download_archive(library, archive, opener=lambda *args, **kwargs: io.BytesIO(raw))
    assert archive.read_bytes() == raw


@pytest.mark.parametrize('corruption', ['digest', 'size'])
def test_authoritative_alternate_still_requires_pinned_integrity(tmp_path, corruption):
    library = dict(MANIFEST['libraries'][0],
                   asset_url='https://api.github.com/repos/yfedoseev/office_oxide/releases/assets/42')
    raw = archive_bytes({name: name.encode() for name in library['required']})
    invalid = raw[:-1] + bytes([raw[-1] ^ 1]) if corruption == 'digest' else raw + b'extra'
    archive = tmp_path / PREPARE.archive_name(library)
    calls = []

    def respond(request, timeout):
        calls.append(request.full_url)
        if request.full_url == library['asset_url']:
            return io.BytesIO(invalid)
        raise urllib.error.URLError('release unavailable')

    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.download_archive(library, archive, opener=respond, sleeper=lambda delay: None)
    assert library['asset_url'] in calls
    assert len(calls) == 3
    assert not archive.exists()
    assert not archive.with_name(archive.name + '.part').exists()


def test_completed_partial_recovers_without_range_416(tmp_path):
    library = MANIFEST['libraries'][0]
    raw = archive_bytes({name: name.encode() for name in library['required']})
    archive, partial = seed_partial(library, tmp_path, raw)
    PREPARE.download_archive(library, archive, opener=no_network)
    assert archive.read_bytes() == raw
    assert not partial.exists()


def test_manifest_change_rejects_old_partial_without_network(tmp_path):
    library = MANIFEST['libraries'][0]
    archive, partial = seed_partial(library, tmp_path, b'old prefix')
    changed = dict(library, sha256='0' * 64)
    with pytest.raises(RuntimeError, match='partial cache does not match'):
        PREPARE.download_archive(changed, archive, opener=no_network)
    assert partial.read_bytes() == b'old prefix'


def test_cache_reused_after_later_dependency_failure(tmp_path):
    first, second = MANIFEST['libraries'][:2]
    cache = tmp_path / 'cache'
    calls = []

    def fail_second(request, timeout):
        calls.append(request.full_url)
        if request.full_url == second['url']:
            raise urllib.error.HTTPError(request.full_url, 404, 'missing', {}, None)
        return io.BytesIO(archive_bytes({name: name.encode() for name in first['required']}))

    with pytest.raises(RuntimeError, match='Native download failed'):
        PREPARE.export_bundle([first, second], cache, tmp_path, opener=fail_second)
    assert not (cache / 'receipt.json').exists()
    assert PREPARE.cached_partial_archive(first, cache)[1]['sha256'] == first['sha256']

    def only_second(request, timeout):
        assert request.full_url == second['url']
        return io.BytesIO(archive_bytes({name: name.encode() for name in second['required']}))

    PREPARE.export_bundle([first, second], cache, tmp_path, opener=only_second)
    PREPARE.export_bundle([first, second], cache, tmp_path, opener=no_network)
    assert len(json.loads((cache / 'receipt.json').read_text())) == 2


def test_self_consistent_cache_tampering_rejected_by_pinned_digest(tmp_path):
    bundle = make_bundle(tmp_path)
    library = MANIFEST['libraries'][0]
    archive = bundle / PREPARE.archive_name(library)
    archive.write_bytes(b'malicious')
    record_path = PREPARE._cache_record_path(library, bundle)
    record = json.loads(record_path.read_text())
    record.update(sha256=hashlib.sha256(b'malicious').hexdigest(), size=9)
    record_path.write_text(json.dumps(record))
    with pytest.raises(RuntimeError):
        PREPARE.install_library(library, tmp_path / 'installed', tmp_path,
                                cache_directory=bundle, offline=True, opener=no_network)


def test_unrecorded_complete_archive_reverified_after_interruption(tmp_path):
    library = MANIFEST['libraries'][0]
    archive = tmp_path / PREPARE.archive_name(library)
    archive.write_bytes(archive_bytes({name: name.encode() for name in library['required']}))
    cached = PREPARE.cached_partial_archive(library, tmp_path)
    assert cached[1]['sha256'] == library['sha256']
    assert PREPARE._cache_record_path(library, tmp_path).exists()


def release_metadata(library):
    tag = library['url'].split('/download/')[1].split('/')[0]
    return {'tag_name': __import__('urllib.parse', fromlist=['unquote']).unquote(tag), 'assets': [{
        'browser_download_url': library['url'], 'size': 123,
        'digest': 'sha256:' + 'a' * 64,
        'url': 'https://api.github.com/repos/' + '/'.join(library['url'].split('/')[3:5]) + '/releases/assets/123',
    }]}


@pytest.mark.parametrize('library', DECLARED_MANIFEST['libraries'], ids=lambda item: item['name'])
def test_resolves_exact_version_authoritative_digest(library):
    metadata = release_metadata(library)

    def respond(request, timeout):
        assert request.full_url.startswith('https://api.github.com/repos/')
        assert '/releases/tags/' in request.full_url
        assert timeout == 30
        return io.BytesIO(json.dumps(metadata).encode())

    result = PREPARE.resolve_library(library, opener=respond)
    assert result['sha256'] == 'a' * 64 and result['size'] == 123
    assert result['url'] == library['url'] and result['version'] == library['version']


@pytest.mark.parametrize('tag_path', ['chromium/7809', 'chromium%2F7809', 'chromium%2f7809'])
def test_pdfium_release_tag_url_spellings_resolve_same_asset(tag_path):
    library = DECLARED_MANIFEST['libraries'][1]
    metadata = {
        'tag_name': 'chromium/7809',
        'assets': [{
            'browser_download_url': 'https://github.com/kognitos/pdfium-static/releases/download/'
                                    + tag_path + '/pdfium-linux-x64-static.tgz',
            'digest': 'sha256:' + 'b' * 64,
            'size': 321,
            'url': 'https://api.github.com/repos/kognitos/pdfium-static/releases/assets/456',
        }],
    }

    def respond(request, timeout):
        assert request.full_url == 'https://api.github.com/repos/kognitos/pdfium-static/releases/tags/chromium%2F7809'
        assert timeout == 30
        return io.BytesIO(json.dumps(metadata).encode())

    result = PREPARE.resolve_library(library, opener=respond)
    assert result['sha256'] == 'b' * 64 and result['size'] == 321
    assert result['asset_url'] == metadata['assets'][0]['url']
    assert result['url'] == library['url'] and result['version'] == '7809'


@pytest.mark.parametrize('changed_url', [
    'http://github.com/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://example.org/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://github.com.evil.invalid/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://user@github.com/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://github.com:444/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://github.com/other/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://github.com/kognitos/pdfium-static-fork/releases/download/chromium/7809/pdfium-linux-x64-static.tgz',
    'https://github.com/kognitos/pdfium-static/releases/download/chromium/7810/pdfium-linux-x64-static.tgz',
    'https://github.com/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-arm64-static.tgz',
    'https://github.com/kognitos/pdfium-static/releases/download/chromium%252F7809/pdfium-linux-x64-static.tgz',
    'https://github.com/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz?download=1',
    'https://github.com/kognitos/pdfium-static/releases/download/chromium/7809/pdfium-linux-x64-static.tgz#other',
    'https://github.com/[invalid',
    None,
])
def test_pdfium_url_equivalence_does_not_change_release_identity(changed_url):
    library = DECLARED_MANIFEST['libraries'][1]
    metadata = release_metadata(library)
    metadata['assets'][0]['browser_download_url'] = changed_url
    with pytest.raises(RuntimeError, match='Missing or duplicate native release asset: pdfium-static'):
        PREPARE.resolve_library(library, opener=lambda *args, **kwargs: io.BytesIO(json.dumps(metadata).encode()))


def test_equivalent_pdfium_urls_still_count_as_duplicate_assets():
    library = DECLARED_MANIFEST['libraries'][1]
    metadata = release_metadata(library)
    metadata['assets'].append(dict(metadata['assets'][0],
                                   browser_download_url=library['url'].replace('%2F', '/')))
    with pytest.raises(RuntimeError, match='Missing or duplicate native release asset: pdfium-static'):
        PREPARE.resolve_library(library, opener=lambda *args, **kwargs: io.BytesIO(json.dumps(metadata).encode()))


@pytest.mark.parametrize('changed_field, value', [
    ('digest', None), ('digest', 'sha256:not-a-digest'), ('size', 0), ('size', True),
    ('url', 'https://api.github.com/repos/other/pdfium-static/releases/assets/456'),
])
def test_equivalent_pdfium_url_retains_authoritative_digest_size_and_api_gates(changed_field, value):
    library = DECLARED_MANIFEST['libraries'][1]
    metadata = release_metadata(library)
    metadata['assets'][0]['browser_download_url'] = library['url'].replace('%2F', '/')
    metadata['assets'][0][changed_field] = value
    with pytest.raises(RuntimeError, match='SHA256 unavailable|Invalid authoritative native'):
        PREPARE.resolve_library(library, opener=lambda *args, **kwargs: io.BytesIO(json.dumps(metadata).encode()))


def test_pdfium_metadata_download_and_offline_bundle_roundtrip(tmp_path):
    library = DECLARED_MANIFEST['libraries'][1]
    files = {name: ('roundtrip:' + name).encode() for name in library['required']}
    raw = archive_bytes(files)
    metadata = release_metadata(library)
    metadata['assets'][0].update(
        browser_download_url=library['url'].replace('%2F', '/'),
        digest='sha256:' + hashlib.sha256(raw).hexdigest(), size=len(raw))
    pinned = PREPARE.resolve_library(
        library, opener=lambda *args, **kwargs: io.BytesIO(json.dumps(metadata).encode()))
    calls = []

    def download(request, timeout):
        calls.append(request.full_url)
        assert request.full_url == library['url']
        return io.BytesIO(raw)

    def disconnected(*args, **kwargs):
        pytest.fail('Offline native installation attempted a network request')

    bundle = tmp_path / 'bundle'
    PREPARE.export_bundle([pinned], bundle, tmp_path, opener=download)
    destination = tmp_path / 'installed'
    record = PREPARE.install_library(pinned, destination, tmp_path, opener=disconnected,
                                     archive_directory=bundle, offline=True)
    assert calls == [library['url']]
    assert record['sha256'] == hashlib.sha256(raw).hexdigest()
    assert record['size'] == len(raw)
    for name, content in files.items():
        assert (destination / name).read_bytes() == content


@pytest.mark.parametrize('change', ['tag', 'digest', 'asset', 'duplicate', 'size', 'api-url'])
def test_bad_authoritative_metadata_fails_closed(change):
    library = DECLARED_MANIFEST['libraries'][0]
    metadata = release_metadata(library)
    if change == 'tag':
        metadata['tag_name'] = 'v99'
    elif change == 'duplicate':
        metadata['assets'] *= 2
    else:
        key = {'digest': 'digest', 'asset': 'browser_download_url', 'size': 'size', 'api-url': 'url'}[change]
        metadata['assets'][0][key] = None
    with pytest.raises((RuntimeError, TypeError)):
        PREPARE.resolve_library(library, opener=lambda *args, **kwargs: io.BytesIO(json.dumps(metadata).encode()))


def test_authoritative_asset_api_alternative_preserves_checksum(tmp_path):
    library = dict(MANIFEST['libraries'][0], asset_url='https://api.github.com/repos/yfedoseev/office_oxide/releases/assets/123')
    raw = archive_bytes({name: name.encode() for name in library['required']})
    calls = []

    def respond(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 403, 'route denied', {}, None)
        assert request.get_header('Accept') == 'application/octet-stream'
        return io.BytesIO(raw)

    archive = tmp_path / PREPARE.archive_name(library)
    PREPARE.download_archive(library, archive, opener=respond, sleeper=lambda delay: None)
    assert calls == [library['url'], library['asset_url']]
    assert archive.read_bytes() == raw


def test_oversized_response_stops_before_writing_unbounded_bytes(tmp_path):
    library = MANIFEST['libraries'][0]
    archive = tmp_path / PREPARE.archive_name(library)

    class OversizedStream(io.BytesIO):
        def read1(self, size):
            assert self.tell() == 0
            return super().read(size)

    with pytest.raises(RuntimeError, match='Native download failed') as failure:
        PREPARE.download_archive(library, archive,
                                 opener=lambda *args, **kwargs: OversizedStream(b'x' * (library['size'] + 1)),
                                 sleeper=lambda delay: None)
    assert 'exceeds authoritative size' in str(failure.value.__cause__)
    assert not archive.exists()
    assert not archive.with_name(archive.name + '.part').exists()
