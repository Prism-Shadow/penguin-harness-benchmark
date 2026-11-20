import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fxc_download', ROOT / 'environment/native-runtime/download.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
PAYLOAD = bytes(range(256)) * 256


class Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *arguments):
        pass

    def do_GET(self):
        self.requests.append((self.path, self.headers.get('Range')))
        if self.path == '/missing':
            self.send_error(404)
            return
        if self.path == '/slow':
            time.sleep(0.2)
        offset = int(self.headers.get('Range', 'bytes=0-').split('=')[1].rstrip('-'))
        self.send_response(206 if offset else 200)
        self.send_header('Content-Length', str(len(PAYLOAD) - offset))
        if offset:
            self.send_header('Content-Range', f'bytes {offset}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}')
        self.end_headers()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(PAYLOAD[offset:])


class HttpDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        except PermissionError as error:
            raise unittest.SkipTest('sandbox forbids local sockets; run HTTP resume tests independently') from error
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        Handler.requests = []
        self.scratch = tempfile.TemporaryDirectory(prefix='fxc-download-')
        self.addCleanup(self.scratch.cleanup)
        self.archive = Path(self.scratch.name) / 'FirefoxSetup62.0.3-win64.exe'
        self.partial = self.archive.with_name(self.archive.name + '.cowork-part')

    def fetch(self, program, paths, seconds=3):
        urls = [self.base + path for path in paths]
        option = '-O' if program == 'wget' else '--output'
        return transport.download(program, [option, str(self.archive), urls[0]], urls, seconds)

    def test_wget_and_curl_resume_real_partial_download(self):
        for program in ('wget', 'curl'):
            with self.subTest(program=program):
                self.partial.write_bytes(PAYLOAD[:4096])
                self.assertEqual(self.fetch(program, ['/archive']), 0)
                self.assertEqual(self.archive.read_bytes(), PAYLOAD)
                self.assertEqual(Handler.requests[-1], ('/archive', 'bytes=4096-'))

    def test_authoritative_fallback_preserves_partial_file(self):
        self.partial.write_bytes(PAYLOAD[:4096])
        self.assertEqual(self.fetch('wget', ['/missing', '/archive']), 0)
        self.assertEqual(self.archive.read_bytes(), PAYLOAD)
        self.assertEqual([path for path, _ in Handler.requests], ['/missing', '/archive'])
        self.assertEqual(Handler.requests[-1][1], 'bytes=4096-')

    def test_failed_attempt_keeps_partial_file_for_next_invocation(self):
        self.partial.write_bytes(PAYLOAD[:2048])
        self.assertEqual(self.fetch('wget', ['/missing']), 86)
        self.assertEqual(self.partial.read_bytes(), PAYLOAD[:2048])
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.fetch('wget', ['/archive']), 0)
        self.assertEqual(self.archive.read_bytes(), PAYLOAD)

    def test_deadline_kills_downloader_and_retains_partial(self):
        self.partial.write_bytes(PAYLOAD[:1024])
        start = time.monotonic()
        self.assertEqual(self.fetch('wget', ['/slow'], seconds=0.05), 86)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(self.partial.read_bytes(), PAYLOAD[:1024])
        self.assertFalse(self.archive.exists())


class TransportPolicyTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='fxc-transport-policy-')
        self.addCleanup(self.scratch.cleanup)
        self.archive = Path(self.scratch.name) / 'FirefoxSetup62.0.3-win64.exe'
        self.partial = self.archive.with_name(self.archive.name + '.cowork-part')

    def test_exact_version_mirrors_and_rejected_urls(self):
        for path in transport.PATHS:
            for host in transport.HOSTS:
                urls = transport.mirrors('https://' + host + path)
                self.assertEqual(urls, ['https://' + target + path for target in transport.HOSTS])
        for url in ('http://archive.mozilla.org' + transport.PATHS[0],
                    'https://evil.example' + transport.PATHS[0],
                    'https://archive.mozilla.org' + transport.PATHS[0].replace('62.0.3', '63.0'),
                    'https://archive.mozilla.org' + transport.PATHS[0] + '?skip-checksum=1',
                    'https://www.7-zip.org/a/7z1900.exe'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                transport.mirrors(url)

    def test_each_mirror_has_a_hard_deadline(self):
        url = 'https://' + transport.HOSTS[0] + transport.PATHS[0]
        with patch.object(transport.subprocess, 'run', side_effect=subprocess.TimeoutExpired('wget', 180)) as run:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(transport.download('wget', ['-O', str(self.archive), url], transport.mirrors(url)), 86)
        self.assertEqual(run.call_count, 3)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['timeout'], 180)
            self.assertIn('--tries=1', call.args[0])

    def test_real_curl_resumes_file_without_network(self):
        source = Path(self.scratch.name) / 'source.exe'
        source.write_bytes(PAYLOAD)
        self.partial.write_bytes(PAYLOAD[:4096])
        url = 'https://' + transport.HOSTS[0] + transport.PATHS[0]
        self.assertEqual(transport.download('curl', ['--output', str(self.archive), url], [source.as_uri()]), 0)
        self.assertEqual(self.archive.read_bytes(), PAYLOAD)
        self.assertFalse(self.partial.exists())

    def test_failed_transport_does_not_publish_or_replace_archive(self):
        self.archive.write_bytes(b'existing input')
        self.partial.write_bytes(PAYLOAD[:4096])
        url = 'https://' + transport.HOSTS[0] + transport.PATHS[0]
        with patch.object(transport.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(transport.download('wget', ['-O', str(self.archive), url], transport.mirrors(url)), 86)
        self.assertEqual(self.archive.read_bytes(), b'existing input')
        self.assertEqual(self.partial.read_bytes(), PAYLOAD[:4096])

    def test_staging_requires_one_explicit_output_file(self):
        for program, option in (('wget', '--output-document'), ('curl', '--output')):
            prepared, partial, destination = transport.staged_output(program, [option + '=' + str(self.archive)])
            self.assertEqual(destination, self.archive)
            self.assertEqual(partial, self.partial)
            self.assertEqual(prepared, [option + '=' + str(self.partial)])
            for arguments in ([], [option], [option, '-'], [option, ''], [option, 'first', option, 'second']):
                with self.subTest(program=program, arguments=arguments), self.assertRaises(ValueError):
                    transport.staged_output(program, arguments)


if __name__ == '__main__':
    unittest.main()
