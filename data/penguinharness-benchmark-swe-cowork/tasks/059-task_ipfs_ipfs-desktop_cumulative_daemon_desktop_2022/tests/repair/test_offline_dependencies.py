import hashlib
import importlib.util
import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


environment = Path(__file__).parents[2] / 'environment'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, environment / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_go = load('prepare_go', 'prepare-offline-go.py')
offline_npm = load('offline_npm', 'offline-npm.py')


def fixture_lock(directory, versions=('0.12.0', '0.13.0'), pinned=True):
    releases = [{'version': version, 'sha512': hashlib.sha512(
        ('checksum fixture ' + version).encode()).hexdigest() if pinned else None} for version in versions]
    lock = directory / 'releases.json'
    lock.write_text(json.dumps({'schema': 'stock-go-ipfs-inputs-v1',
                                'platform': 'linux-amd64', 'releases': releases}))
    return lock


class OfflineDependenciesTests(unittest.TestCase):
    def test_cached_versions_and_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            mirror = Path(temporary) / 'mirror'
            cache.mkdir()
            for version in ('0.12.0', '0.13.0'):
                archive = cache / f'go-ipfs_v{version}_linux-amd64.tar.gz'
                payload = ('checksum fixture ' + version).encode()
                archive.write_bytes(payload)
                Path(str(archive) + '.sha512').write_text(hashlib.sha512(payload).hexdigest() + '  archive\n')
            lock = fixture_lock(Path(temporary))
            with patch.object(prepare_go, 'transfer', side_effect=AssertionError('unexpected network')):
                prepare_go.prepare(cache, mirror, '0.12.0', lock)
            self.assertEqual((mirror / 'go-ipfs/versions').read_text(), 'v0.12.0\nv0.13.0\n')
            metadata = json.loads((mirror / 'go-ipfs/v0.13.0/dist.json').read_text())
            self.assertEqual(metadata['platforms']['linux']['archs']['amd64']['link'], '/go-ipfs_v0.13.0_linux-amd64.tar.gz')
            archive.write_bytes(b'corrupted bytes')
            with self.assertRaisesRegex(ValueError, 'SHA512 mismatch'):
                prepare_go.prepare(cache, mirror, '0.12.0', lock)
            self.assertFalse((mirror / 'go-ipfs/versions').exists())

    def test_missing_baseline_fetches_both_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            requests = []
            payload = b'checksum fixture 0.12.0'
            def fetch(url, target, resume):
                requests.append(url)
                target.write_bytes(hashlib.sha512(payload).hexdigest().encode() if url.endswith('.sha512') else payload)
            lock = fixture_lock(Path(temporary), ('0.12.0',), pinned=False)
            with patch.object(prepare_go, 'transfer', side_effect=fetch):
                prepare_go.prepare(Path(temporary) / 'cache', Path(temporary) / 'mirror', '0.12.0', lock, download=True)
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(url.startswith('https://dist.ipfs.io/go-ipfs/v0.12.0/') for url in requests))
            release = json.loads(lock.read_text())['releases'][0]
            self.assertEqual(release['sha512'], hashlib.sha512(payload).hexdigest())
            self.assertEqual(release['checksum_source'], requests[0])
            with patch.object(prepare_go, 'transfer', side_effect=AssertionError('unexpected network')):
                prepare_go.prepare(Path(temporary) / 'cache', Path(temporary) / 'mirror', '0.12.0', lock)

    def test_real_loopback_transport_and_exit_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            mirror = Path(temporary)
            (mirror / 'go-ipfs').mkdir()
            (mirror / 'go-ipfs/versions').write_text('v0.12.0\n')
            program = """import os, sys, urllib.request
assert urllib.request.urlopen(os.environ['GO_IPFS_DIST_URL'] + '/go-ipfs/versions').read() == b'v0.12.0\\n'
assert os.environ['npm_config_jobs'] == '2'
assert os.environ['MAKEFLAGS'] == '-j2'
sys.exit(17)
"""
            with patch.dict(os.environ, {'HTTP_PROXY': 'http://invalid.test:1'}):
                self.assertEqual(offline_npm.run([sys.executable, '-c', program], mirror), 17)

    def test_missing_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                offline_npm.run([sys.executable, '-c', 'raise SystemExit(0)'], Path(temporary))


class ArchiveAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / 'cache'
        self.mirror = self.root / 'mirror'
        self.payload = b'checksum fixture 0.12.0'
        self.digest = hashlib.sha512(self.payload).hexdigest()
        self.archive = self.root / 'go-ipfs_v0.12.0_linux-amd64.tar.gz'
        self.partial = self.archive.with_name(self.archive.name + '.partial')
        self.lock = fixture_lock(self.root, ('0.12.0',))

    def validate(self, path):
        prepare_go.verify_archive(path, self.digest)

    def test_resume_and_atomic_promotion(self):
        self.partial.write_bytes(self.payload[:5])
        def transfer(url, target, resume):
            self.assertTrue(resume)
            self.assertEqual(target.read_bytes(), self.payload[:5])
            self.assertFalse(self.archive.exists())
            with target.open('ab') as stream:
                stream.write(self.payload[5:])
        with patch.object(prepare_go, 'transfer', side_effect=transfer):
            prepare_go.acquire(['https://primary.test/archive'], self.archive, self.validate)
        self.assertEqual(self.archive.read_bytes(), self.payload)
        self.assertFalse(self.partial.exists())

    def test_range_unsupported_restarts_once(self):
        self.partial.write_bytes(b'old partial')
        def transfer(url, target, resume):
            if resume:
                raise OSError('range unsupported')
            target.write_bytes(self.payload)
        with patch.object(prepare_go, 'transfer', side_effect=transfer) as mocked:
            prepare_go.acquire(['https://primary.test/archive'], self.archive, self.validate)
        self.assertEqual(mocked.call_count, 2)
        self.validate(self.archive)

    def test_primary_unreachable_uses_fallback(self):
        def transfer(url, target, resume):
            if 'primary' in url:
                raise OSError('network unreachable')
            target.write_bytes(self.payload)
        with patch.object(prepare_go, 'transfer', side_effect=transfer) as mocked:
            origin = prepare_go.acquire(['https://primary.test/archive', 'https://fallback.test/archive'],
                                        self.archive, self.validate)
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(origin, 'https://fallback.test/archive')
        self.validate(self.archive)

    def test_all_sources_bounded_and_partial_retained(self):
        def transfer(url, target, resume):
            target.write_bytes(self.payload[:5])
            raise subprocess.TimeoutExpired(['curl'], 35)
        with patch.object(prepare_go, 'transfer', side_effect=transfer) as mocked:
            with self.assertRaisesRegex(RuntimeError, 'verified inputs were preserved'):
                prepare_go.acquire(['https://primary.test/archive', 'https://fallback.test/archive'],
                                   self.archive, self.validate)
        self.assertEqual(mocked.call_count, 4)
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.partial.read_bytes(), self.payload[:5])

    def test_corrupt_download_never_promoted(self):
        def transfer(url, target, resume):
            target.write_bytes(b'corruption')
        with patch.object(prepare_go, 'transfer', side_effect=transfer):
            with self.assertRaisesRegex(RuntimeError, 'SHA512 mismatch'):
                prepare_go.acquire(['https://primary.test/archive'], self.archive, self.validate)
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.partial.exists())

    def test_valid_partial_can_finish_without_network(self):
        self.partial.write_bytes(self.payload)
        with patch.object(prepare_go, 'transfer', side_effect=AssertionError('unexpected network')):
            prepare_go.acquire(['https://primary.test/archive'], self.archive, self.validate)
        self.validate(self.archive)

    def test_offline_missing_input_fails_without_network(self):
        with patch.object(prepare_go, 'transfer', side_effect=AssertionError('unexpected network')):
            with self.assertRaisesRegex(FileNotFoundError, 'missing pinned archive'):
                prepare_go.prepare(self.cache, self.mirror, '0.12.0', self.lock)
        self.assertFalse((self.mirror / 'go-ipfs/versions').exists())

    def test_local_import_is_verified_independent_copy(self):
        self.archive.write_bytes(self.payload)
        with patch.object(prepare_go, 'transfer', side_effect=AssertionError('unexpected network')):
            prepare_go.prepare(self.cache, self.mirror, '0.12.0', self.lock, source=self.root)
        imported = self.cache / self.archive.name
        self.assertNotEqual(imported.stat().st_ino, self.archive.stat().st_ino)
        self.validate(imported)
        self.assertEqual((self.mirror / 'go-ipfs/versions').read_text(), 'v0.12.0\n')

    def test_modified_local_archive_and_sidecar_cannot_override_pin(self):
        self.archive.write_bytes(b'untrusted')
        self.archive.with_name(self.archive.name + '.sha512').write_text(hashlib.sha512(b'untrusted').hexdigest())
        with self.assertRaisesRegex(ValueError, 'SHA512 mismatch'):
            prepare_go.prepare(self.cache, self.mirror, '0.12.0', self.lock, source=self.root)
        self.assertFalse((self.cache / self.archive.name).exists())

    def test_unpinned_checksum_never_trusts_local_partial(self):
        self.lock = fixture_lock(self.root, ('0.12.0',), pinned=False)
        self.cache.mkdir()
        forged = self.cache / (self.archive.name + '.sha512.partial')
        forged.write_text(self.digest)
        with patch.object(prepare_go, 'transfer', side_effect=OSError('offline')) as mocked:
            with self.assertRaisesRegex(RuntimeError, 'archive preparation failed'):
                prepare_go.prepare(self.cache, self.mirror, '0.12.0', self.lock, download=True)
        self.assertEqual(mocked.call_count, 4)
        self.assertIsNone(json.loads(self.lock.read_text())['releases'][0]['sha512'])

    def test_checksum_record_rejects_wrong_filename_and_malformed_digest(self):
        for record in (self.digest + ' wrong-version.tar.gz', 'abcd', self.digest + ' archive extra', ''):
            self.partial.write_text(record)
            with self.assertRaises(ValueError):
                prepare_go.parse_checksum(self.partial, self.archive.name)

    def test_transfer_enforces_network_bounds(self):
        with patch.object(prepare_go.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as mocked:
            prepare_go.transfer('https://primary.test/archive', self.partial, True)
        command = mocked.call_args.args[0]
        self.assertEqual(mocked.call_args.kwargs['timeout'], 35)
        for option, expected in (('--connect-timeout', '5'), ('--max-time', '30'),
                                 ('--proto', '=https'), ('--proto-redir', '=https'), ('--continue-at', '-')):
            self.assertEqual(command[command.index(option) + 1], expected)


if __name__ == '__main__':
    unittest.main()
