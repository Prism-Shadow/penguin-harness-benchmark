import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error

from test_render_runtime import runtime


class Response(io.BytesIO):
    def __init__(self, content=b'', status=200, headers=None, interrupt=False):
        super().__init__(content)
        self.status = status
        self.headers = headers or {}
        self.interrupt = interrupt

    def read(self, size=-1):
        if self.interrupt and self.tell():
            raise runtime.http.client.RemoteDisconnected('release connection interrupted')
        return super().read(size)

    def read1(self, size=-1):
        return self.read(size)


class RuntimePreparationFixture:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.archive = b'verified tiny archive fixture, not an Electron executable'
        self.manifest = f'{hashlib.sha256(self.archive).hexdigest()} *{runtime.ARCHIVE}\n'.encode()
        self.pins = {runtime.ARCHIVE: hashlib.sha256(self.archive).hexdigest(),
                     runtime.MANIFEST: hashlib.sha256(self.manifest).hexdigest()}
        pins = patch.object(runtime, 'PINNED_DIGESTS', self.pins)
        pins.start()
        self.addCleanup(pins.stop)

    def download(self, attempts=1):
        return runtime.download(runtime.ARCHIVE, self.directory / runtime.ARCHIVE,
                                time.monotonic() + 3, attempts)


class RuntimePreparationTests(RuntimePreparationFixture, unittest.TestCase):
    def test_interrupted_response_resumes_in_next_invocation(self):
        prefix = self.archive[:13]
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(prefix, interrupt=True)):
            with self.assertRaisesRegex(RuntimeError, 'resume with the same cache'):
                self.download()
        partial = self.directory / (runtime.ARCHIVE + '.part')
        self.assertEqual(partial.read_bytes(), prefix)
        self.assertFalse((self.directory / runtime.ARCHIVE).exists())
        headers = {'Content-Range': f'bytes 13-{len(self.archive) - 1}/{len(self.archive)}'}
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive[13:], 206, headers)) as opened:
            self.download()
        self.assertEqual(opened.call_args.args[0].get_header('Range'), 'bytes=13-')
        self.assertEqual((self.directory / runtime.ARCHIVE).read_bytes(), self.archive)
        self.assertFalse(partial.exists())

    def test_range_ignored_restarts_without_duplicate_prefix(self):
        (self.directory / (runtime.ARCHIVE + '.part')).write_bytes(self.archive[:5])
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive)):
            self.download()
        self.assertEqual((self.directory / runtime.ARCHIVE).read_bytes(), self.archive)

    def test_invalid_range_never_appends(self):
        partial = self.directory / (runtime.ARCHIVE + '.part')
        partial.write_bytes(self.archive[:5])
        for header in ['bytes 0-1/2', 'bytes 5-8/8', 'invalid']:
            with self.subTest(header=header), patch.object(runtime.urllib.request, 'urlopen', return_value=Response(b'junk', 206, {'Content-Range': header})):
                with self.assertRaises(RuntimeError):
                    self.download()
            self.assertEqual(partial.read_bytes(), self.archive[:5])

    def test_truncated_response_retains_bytes(self):
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive[:5], headers={'Content-Length': str(len(self.archive))})):
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                self.download()
        self.assertEqual((self.directory / (runtime.ARCHIVE + '.part')).read_bytes(), self.archive[:5])

    def test_valid_incomplete_range_retains_bytes(self):
        partial = self.directory / (runtime.ARCHIVE + '.part')
        partial.write_bytes(self.archive[:5])
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive[5:10], 206, {'Content-Range': f'bytes 5-9/{len(self.archive)}'})):
            with self.assertRaisesRegex(RuntimeError, 'more bytes required'):
                self.download()
        self.assertEqual(partial.read_bytes(), self.archive[:10])

    def test_wrong_digest_is_not_promoted(self):
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(b'wrong bytes')):
            with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
                self.download()
        self.assertFalse((self.directory / runtime.ARCHIVE).exists())
        self.assertFalse((self.directory / (runtime.ARCHIVE + '.part')).exists())

    def test_oversized_response_is_rejected_before_writing(self):
        headers = {'Content-Length': str(runtime.MAX_BYTES[runtime.ARCHIVE] + 1)}
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(b'', headers=headers)):
            with self.assertRaisesRegex(RuntimeError, 'size limit'):
                self.download()
        self.assertFalse((self.directory / runtime.ARCHIVE).exists())

    def test_verified_cache_and_complete_partial_do_not_use_network(self):
        (self.directory / runtime.MANIFEST).write_bytes(self.manifest)
        (self.directory / (runtime.ARCHIVE + '.part')).write_bytes(self.archive)
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=AssertionError('network must not run')):
            runtime.prepare(self.directory)
            runtime.prepare(self.directory)
        self.assertEqual((self.directory / runtime.ARCHIVE).read_bytes(), self.archive)

    def test_corrupt_cache_is_rehashed_and_repaired(self):
        (self.directory / runtime.ARCHIVE).write_bytes(b'corrupt cache')
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive)) as opened:
            self.download()
        opened.assert_called_once()
        self.assertEqual((self.directory / runtime.ARCHIVE).read_bytes(), self.archive)

    def test_seed_inputs_are_verified_before_offline_reuse(self):
        seed = self.directory / 'seed'
        seed.mkdir()
        (seed / runtime.ARCHIVE).write_bytes(self.archive)
        (seed / runtime.MANIFEST).write_bytes(self.manifest)
        cache = self.directory / 'cache'
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=AssertionError('network must not run')):
            runtime.prepare(cache, seed_assets=seed)
            (seed / runtime.MANIFEST).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'seed asset SHA256 mismatch'):
                runtime.prepare(cache, seed_assets=seed)
        self.assertEqual((cache / runtime.ARCHIVE).read_bytes(), self.archive)

    def test_retries_are_finite_and_rotate_independent_routes(self):
        with patch.object(runtime, 'transfer', side_effect=runtime.http.client.RemoteDisconnected('disconnect')) as transfer, \
                patch.object(runtime.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                self.download(attempts=4)
        self.assertEqual([call.args[2] for call in transfer.call_args_list],
                         ['npmmirror', 'github-release', 'github-api', 'npmmirror'])

    def test_416_discards_invalid_partial_before_retry(self):
        partial = self.directory / (runtime.ARCHIVE + '.part')
        partial.write_bytes(b'stale range')
        with patch.object(runtime, 'transfer', side_effect=urllib.error.HTTPError('url', 416, 'range', {}, None)):
            with self.assertRaises(RuntimeError):
                self.download()
        self.assertFalse(partial.exists())

    def test_wall_deadline_interrupts_stalled_network(self):
        started = time.monotonic()
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=lambda *args, **kwargs: time.sleep(5)):
            with self.assertRaises((RuntimeError, TimeoutError)):
                runtime.prepare(self.directory, timeout=0.05, attempts=6)
        self.assertLess(time.monotonic() - started, 1)

    def test_nested_attempt_timer_restores_total_deadline(self):
        with self.assertRaises(TimeoutError):
            with runtime.time_limit(0.05):
                with runtime.time_limit(0.02):
                    pass
                time.sleep(5)

    def test_invalid_limits_fail_without_network(self):
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=AssertionError('network must not run')):
            for timeout, attempts in [(0, 1), (float('inf'), 1), (float('nan'), 1), (1801, 1), (1, 0), (1, 13)]:
                with self.subTest(timeout=timeout, attempts=attempts), self.assertRaises(ValueError):
                    runtime.prepare(self.directory, timeout=timeout, attempts=attempts)

    def test_official_api_selects_exact_asset_and_tag(self):
        asset = {'name': runtime.ARCHIVE, 'url': 'https://api.github.com/repos/electron/electron/releases/assets/123'}
        metadata = {'tag_name': 'v9.2.1', 'assets': [asset]}
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(json.dumps(metadata).encode())):
            self.assertEqual(runtime.asset_url(runtime.ARCHIVE, 'github-api'), asset['url'])
        for invalid in [dict(metadata, tag_name='v6.0.0'), dict(metadata, assets=[asset, asset]),
                        dict(metadata, assets=[dict(asset, url='https://untrusted.invalid/binary')])]:
            with self.subTest(metadata=invalid), patch.object(runtime.urllib.request, 'urlopen', return_value=Response(json.dumps(invalid).encode())):
                with self.assertRaises(ValueError):
                    runtime.asset_url(runtime.ARCHIVE, 'github-api')

    def test_cache_lock_prevents_concurrent_writers(self):
        with (self.directory / '.preparation.lock').open('a') as lock:
            runtime.fcntl.flock(lock, runtime.fcntl.LOCK_EX | runtime.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                runtime.prepare(self.directory)

    def test_prepare_only_cli_reuses_cache_without_installing(self):
        (self.directory / runtime.MANIFEST).write_bytes(self.manifest)
        (self.directory / runtime.ARCHIVE).write_bytes(self.archive)
        destination = self.directory / 'must-not-exist' / 'installed'
        with patch('sys.argv', ['install-render-runtime.py', '--prepare-only', '--cache', str(self.directory),
                                '--destination', str(destination)]), \
                patch.object(runtime.urllib.request, 'urlopen', side_effect=AssertionError('network must not run')):
            runtime.main()
        self.assertFalse(destination.parent.exists())

    def test_api_download_requests_binary_from_official_asset_endpoint(self):
        url = 'https://api.github.com/repos/electron/electron/releases/assets/123'
        metadata = {'tag_name': 'v9.2.1', 'assets': [{'name': runtime.ARCHIVE, 'url': url}]}
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=[Response(json.dumps(metadata).encode()), Response(self.archive)]) as opened:
            partial = self.directory / (runtime.ARCHIVE + '.part')
            runtime.transfer(runtime.ARCHIVE, partial, 'github-api')
        self.assertEqual(opened.call_args_list[0].args[0].full_url, runtime.API_RELEASE)
        self.assertEqual(opened.call_args.args[0].full_url, url)
        self.assertEqual(opened.call_args.args[0].get_header('Accept'), 'application/octet-stream')
        self.assertTrue(runtime.verified(partial, runtime.ARCHIVE))

    def test_mirror_uses_exact_version_without_release_api(self):
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=AssertionError('no metadata request')):
            for name in [runtime.ARCHIVE, runtime.MANIFEST]:
                self.assertEqual(runtime.asset_url(name, 'npmmirror'),
                                 'https://npmmirror.com/mirrors/electron/v9.2.1/' + name)
            for name, source in [('electron-v6.0.0-linux-x64.zip', 'npmmirror'),
                                 (runtime.ARCHIVE, 'http://untrusted.invalid')]:
                with self.assertRaises(ValueError):
                    runtime.asset_url(name, source)

    def test_verified_mirror_download_does_not_require_github(self):
        def mirror(request, **kwargs):
            self.assertTrue(request.full_url.startswith(runtime.MIRROR_RELEASE + '/'))
            return Response(self.manifest if request.full_url.endswith(runtime.MANIFEST) else self.archive)

        with patch.object(runtime.urllib.request, 'urlopen', side_effect=mirror) as opened:
            runtime.prepare(self.directory)
        self.assertEqual(opened.call_count, 2)
        self.assertEqual((self.directory / runtime.ARCHIVE).read_bytes(), self.archive)

    def test_bad_mirror_bytes_do_not_change_pins_or_bypass_fallback(self):
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=[Response(b'tampered mirror'), Response(self.archive)]) as opened, \
                patch.object(runtime.time, 'sleep'):
            self.download(attempts=2)
        self.assertEqual([call.args[0].full_url for call in opened.call_args_list],
                         [runtime.MIRROR_RELEASE + '/' + runtime.ARCHIVE, runtime.RELEASE + '/' + runtime.ARCHIVE])
        self.assertEqual(runtime.PINNED_DIGESTS, self.pins)
        self.assertTrue(runtime.verified(self.directory / runtime.ARCHIVE, runtime.ARCHIVE))

    def test_source_switch_resumes_the_same_authenticated_asset(self):
        prefix = self.archive[:13]
        suffix_headers = {'Content-Range': f'bytes 13-{len(self.archive) - 1}/{len(self.archive)}'}
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=[
                Response(prefix, interrupt=True), Response(self.archive[13:], 206, suffix_headers)]) as opened, \
                patch.object(runtime.time, 'sleep'):
            self.download(attempts=2)
        self.assertEqual(opened.call_args.args[0].get_header('Range'), 'bytes=13-')
        self.assertEqual(opened.call_args.args[0].full_url, runtime.RELEASE + '/' + runtime.ARCHIVE)
        self.assertTrue(runtime.verified(self.directory / runtime.ARCHIVE, runtime.ARCHIVE))

    def test_streaming_retains_short_read_before_socket_stalls(self):
        class StalledResponse(Response):
            def read(self, size=-1):
                raise AssertionError('buffered read can lose in-flight bytes on timeout')

            def read1(self, size=-1):
                if self.tell():
                    raise TimeoutError('socket stalled')
                return io.BytesIO.read(self, 7)

        with patch.object(runtime.urllib.request, 'urlopen', return_value=StalledResponse(self.archive)):
            with self.assertRaisesRegex(RuntimeError, 'socket stalled'):
                self.download()
        self.assertEqual((self.directory / (runtime.ARCHIVE + '.part')).read_bytes(), self.archive[:7])

    def test_all_unavailable_sources_remain_bounded_and_report_each_route(self):
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=urllib.error.URLError('unavailable')) as opened, \
                patch.object(runtime.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO) as output:
            with self.assertRaises(RuntimeError):
                self.download(attempts=3)
        self.assertEqual(opened.call_count, 3)
        for source in runtime.SOURCES:
            self.assertIn('source=' + source, output.getvalue())
        self.assertFalse((self.directory / runtime.ARCHIVE).exists())

    def test_missing_release_routes_do_not_consume_retries_twice(self):
        for status in [404, 410]:
            with self.subTest(status=status):
                calls = []

                def transfer(name, partial, source):
                    calls.append(source)
                    if source == 'npmmirror':
                        raise urllib.error.HTTPError('url', status, 'missing', {}, None)
                    raise TimeoutError('slow but retryable')

                with patch.object(runtime, 'transfer', side_effect=transfer), patch.object(runtime.time, 'sleep'):
                    with self.assertRaisesRegex(RuntimeError, 'resume with the same cache'):
                        self.download(attempts=6)
                self.assertEqual(calls, ['npmmirror', 'github-release', 'github-api',
                                         'github-release', 'github-api', 'github-release'])

    def test_all_missing_routes_stop_without_extra_backoff(self):
        error = urllib.error.HTTPError('url', 404, 'missing', {}, None)
        with patch.object(runtime, 'transfer', side_effect=error) as transfer, patch.object(runtime.time, 'sleep') as sleep:
            with self.assertRaises(RuntimeError):
                self.download(attempts=6)
        self.assertEqual(transfer.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_missing_route_does_not_delete_partial_or_disable_next_preparation(self):
        partial = self.directory / (runtime.ARCHIVE + '.part')
        partial.write_bytes(self.archive[:13])
        error = urllib.error.HTTPError('url', 404, 'missing', {}, None)
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(RuntimeError):
                self.download()
        self.assertEqual(partial.read_bytes(), self.archive[:13])
        headers = {'Content-Range': f'bytes 13-{len(self.archive) - 1}/{len(self.archive)}'}
        with patch.object(runtime.urllib.request, 'urlopen', return_value=Response(self.archive[13:], 206, headers)) as opened:
            self.download()
        self.assertEqual(opened.call_args.args[0].full_url, runtime.MIRROR_RELEASE + '/' + runtime.ARCHIVE)
        self.assertEqual(opened.call_args.args[0].get_header('Range'), 'bytes=13-')
        self.assertTrue(runtime.verified(self.directory / runtime.ARCHIVE, runtime.ARCHIVE))

    def test_real_http_response_parser_preserves_and_resumes_truncated_body(self):
        class BufferedSocket:
            def __init__(self, data):
                self.data = data

            def makefile(self, mode):
                return io.BytesIO(self.data)

        first = f'HTTP/1.1 200 OK\r\nContent-Length: {len(self.archive)}\r\n\r\n'.encode() + self.archive[:13]
        second = (f'HTTP/1.1 206 Partial Content\r\nContent-Length: {len(self.archive) - 13}\r\n'
                  f'Content-Range: bytes 13-{len(self.archive) - 1}/{len(self.archive)}\r\n\r\n').encode() + self.archive[13:]
        responses = [runtime.http.client.HTTPResponse(BufferedSocket(content)) for content in [first, second]]
        for response in responses:
            response.begin()
        with patch.object(runtime.urllib.request, 'urlopen', side_effect=responses) as opened, patch.object(runtime.time, 'sleep'):
            self.download(attempts=2)
        self.assertEqual(opened.call_args.args[0].get_header('Range'), 'bytes=13-')
        self.assertTrue(runtime.verified(self.directory / runtime.ARCHIVE, runtime.ARCHIVE))


class RuntimeHTTPTransportTests(RuntimePreparationFixture, unittest.TestCase):
    def test_real_http_interruption_range_resume_and_checksum(self):
        for tampered in [False, True]:
            with self.subTest(tampered=tampered):
                destination = self.directory / runtime.ARCHIVE
                destination.unlink(missing_ok=True)
                archive = self.archive
                requests = []

                class Handler(BaseHTTPRequestHandler):
                    def do_GET(self):
                        requests.append((self.path, self.headers.get('Range')))
                        if len(requests) == 1:
                            self.send_response(200)
                            self.send_header('Content-Length', str(len(archive)))
                            self.end_headers()
                            self.wfile.write(archive[:13])
                        else:
                            suffix = b'x' * len(archive[13:]) if tampered else archive[13:]
                            self.send_response(206)
                            self.send_header('Content-Range', f'bytes 13-{len(archive) - 1}/{len(archive)}')
                            self.send_header('Content-Length', str(len(suffix)))
                            self.end_headers()
                            self.wfile.write(suffix)

                    def log_message(self, format, *args):
                        pass

                with HTTPServer(('127.0.0.1', 0), Handler) as server:
                    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
                    worker.start()
                    try:
                        endpoint = f'http://127.0.0.1:{server.server_port}/v9.2.1/{runtime.ARCHIVE}'
                        with patch.object(runtime, 'asset_url', return_value=endpoint), patch.object(runtime.time, 'sleep'):
                            if tampered:
                                with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
                                    self.download(attempts=2)
                                self.assertFalse(destination.exists())
                            else:
                                self.download(attempts=2)
                                self.assertTrue(runtime.verified(destination, runtime.ARCHIVE))
                    finally:
                        server.shutdown()
                        worker.join(timeout=1)
                        self.assertFalse(worker.is_alive())
                self.assertEqual(requests, [(f'/v9.2.1/{runtime.ARCHIVE}', None),
                                            (f'/v9.2.1/{runtime.ARCHIVE}', 'bytes=13-')])


if __name__ == '__main__':
    unittest.main()
