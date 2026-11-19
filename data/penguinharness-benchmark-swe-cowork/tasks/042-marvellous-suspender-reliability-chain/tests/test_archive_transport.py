import hashlib
import io
import json
import time
import unittest
import urllib.request
from unittest.mock import patch

import test_dependency_preparation as dependency_tests


preparation = dependency_tests.preparation


class InterruptedBody(io.BytesIO):
    def read(self, size=-1):
        if self.tell():
            raise OSError('connection interrupted')
        return super().read(size)


class ArchiveTransportTests(unittest.TestCase):
    setUp = dependency_tests.DependencyPreparationTests.setUp
    make_archive = dependency_tests.DependencyPreparationTests.make_archive
    response = dependency_tests.DependencyPreparationTests.response
    cache_archive = dependency_tests.DependencyPreparationTests.cache_archive

    def partial(self):
        return self.archives / (self.checksum + '.download')

    def target(self):
        return self.archives / (self.checksum + '.tgz')

    def ranged(self, start, origin=None):
        response = self.response(self.content[start:], origin)
        response.status = 206
        response.headers['Content-Range'] = f'bytes {start}-{len(self.content) - 1}/{len(self.content)}'
        return response

    def fetch(self, offline=False, deadline=None):
        return preparation.fetch_archive(self.checksum, self.url, self.archives, [], offline, deadline=deadline)

    def test_interrupted_canonical_transfer_resumes_on_checksum_pinned_mirror(self):
        prefix = self.content[:47]
        first = InterruptedBody(prefix)
        first.status = 200
        first.headers = {'Content-Length': str(len(self.content))}
        first.geturl = lambda: self.url
        mirror = self.url.replace('registry.npmjs.org', 'registry.yarnpkg.com')
        with patch.object(preparation, 'open_archive', side_effect=[first, self.ranged(len(prefix), mirror)]) as network:
            self.assertEqual(self.fetch().read_bytes(), self.content)
            requests = [call.args[0] for call in network.call_args_list]
            self.assertEqual([request.full_url for request in requests], [self.url, mirror])
            self.assertIsNone(requests[0].get_header('Range'))
            self.assertEqual(requests[1].get_header('Range'), 'bytes=47-')
            self.assertEqual(requests[1].get_header('Accept-encoding'), 'identity')
        self.assertFalse(self.partial().exists())
        with patch.object(preparation, 'open_archive') as network:
            self.assertEqual(self.fetch(offline=True).read_bytes(), self.content)
            network.assert_not_called()

    def test_partial_survives_failed_attempt_then_reentry(self):
        prefix = self.content[:59]
        response = self.response(prefix)
        response.headers['Content-Length'] = str(len(self.content))
        with patch.object(preparation, 'open_archive', side_effect=[response, TimeoutError()]):
            with self.assertRaisesRegex(RuntimeError, 'two attempts'):
                self.fetch()
        self.assertEqual(self.partial().read_bytes(), prefix)
        self.assertFalse(self.target().exists())
        with patch.object(preparation, 'open_archive', return_value=self.ranged(len(prefix))) as network:
            self.assertEqual(self.fetch().read_bytes(), self.content)
            self.assertEqual(network.call_args.args[0].get_header('Range'), 'bytes=59-')

    def test_server_ignoring_range_restarts_not_appends(self):
        self.partial().write_bytes(b'old incomplete bytes')
        with patch.object(preparation, 'open_archive', return_value=self.response(self.content)):
            self.assertEqual(self.fetch().read_bytes(), self.content)

    def test_complete_partial_is_reverified_without_network(self):
        self.partial().write_bytes(self.content)
        with patch.object(preparation, 'open_archive') as network:
            self.assertEqual(self.fetch().read_bytes(), self.content)
            network.assert_not_called()

    def test_wrong_range_or_total_cannot_publish(self):
        for content_range in ['bytes 0-6/7', 'bytes 13-20/100', 'garbage', 'bytes 13-33554432/33554433',
                              f'bytes 12-{len(self.content) - 1}/{len(self.content)}']:
            with self.subTest(content_range=content_range):
                self.partial().write_bytes(self.content[:13])
                response = self.ranged(13)
                response.headers['Content-Range'] = content_range
                with patch.object(preparation, 'open_archive', return_value=response):
                    with self.assertRaisesRegex(ValueError, 'range'):
                        self.fetch()
                self.assertFalse(self.target().exists())
                self.assertEqual(self.partial().read_bytes(), self.content[:13])

    def test_wrong_mirror_bytes_never_publish_or_retry_as_valid(self):
        mirror = self.url.replace('registry.npmjs.org', 'registry.yarnpkg.com')
        with patch.object(preparation, 'open_archive', side_effect=[TimeoutError(), self.response(b'tampered mirror', mirror)]) as network:
            with self.assertRaisesRegex(ValueError, 'integrity'):
                self.fetch()
            self.assertEqual(network.call_count, 2)
        self.assertFalse(self.target().exists())

    def test_redirect_is_restricted_before_opening_foreign_origin(self):
        handler = preparation.ArchiveRedirectHandler()
        request = urllib.request.Request(self.url, headers={'Range': 'bytes=13-'})
        request.allowed_origins = preparation.archive_origins(self.url)
        for location in ['http://registry.npmjs.org/x.tgz', 'https://foreign.invalid/a.tgz',
                         self.url + '?token=value', self.url.replace('1.2.3', '1.2.4')]:
            with self.subTest(location=location):
                with self.assertRaisesRegex(ValueError, 'approved origin'):
                    handler.redirect_request(request, None, 302, 'redirect', {}, location)
        redirected = handler.redirect_request(request, None, 302, 'redirect', {}, request.allowed_origins[1])
        self.assertEqual(redirected.get_header('Range'), 'bytes=13-')
        self.assertEqual(redirected.allowed_origins, request.allowed_origins)

    def test_final_response_origin_checked_even_with_injected_transport(self):
        with patch.object(preparation, 'open_archive', return_value=self.response(self.content, 'https://foreign.invalid/a.tgz')):
            with self.assertRaisesRegex(ValueError, 'approved origin'):
                self.fetch()
        self.assertFalse(self.target().exists())

    def test_expired_deadline_performs_no_network(self):
        with patch.object(preparation, 'open_archive') as network:
            with self.assertRaisesRegex(RuntimeError, 'two attempts'):
                self.fetch(deadline=time.monotonic() - 1)
            network.assert_not_called()
        self.assertFalse(self.target().exists())

    def test_slow_body_checks_shared_deadline(self):
        with patch.object(preparation.time, 'monotonic', side_effect=[0, 0, 2, 2]):
            with patch.object(preparation, 'open_archive', return_value=self.response(self.content)) as network:
                with self.assertRaisesRegex(RuntimeError, 'two attempts'):
                    self.fetch(deadline=1)
                self.assertEqual(network.call_count, 1)
                self.assertLessEqual(network.call_args.args[1], 1)
        self.assertFalse(self.target().exists())

    def test_partial_symlink_rejected_without_writing_target(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'unchanged')
        self.partial().symlink_to(outside)
        with patch.object(preparation, 'open_archive') as network:
            with self.assertRaisesRegex(ValueError, 'Unsafe partial'):
                self.fetch()
            network.assert_not_called()
        self.assertEqual(outside.read_bytes(), b'unchanged')

    def test_existing_task_npm_cache_reused_with_original_integrity(self):
        self.cache_archive()
        preparation.prepare(self.project, self.state, offline=True, budget=60)
        self.target().unlink()
        with patch.object(preparation, 'open_archive') as network:
            result = preparation.prepare(self.project, self.state, offline=True, budget=60)
            network.assert_not_called()
        self.assertTrue(result['offline_install'])
        self.assertEqual(hashlib.sha512(self.target().read_bytes()).hexdigest(), self.checksum)
        self.assertEqual(json.loads((self.project / 'package-lock.json').read_text()), self.lock)


if __name__ == '__main__':
    unittest.main()
