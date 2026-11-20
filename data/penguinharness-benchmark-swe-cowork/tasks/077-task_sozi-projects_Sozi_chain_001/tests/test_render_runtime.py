import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile


source = Path(__file__).resolve().parents[1] / 'environment/install-render-runtime.py'
specification = importlib.util.spec_from_file_location('render_runtime', source)
runtime = importlib.util.module_from_spec(specification)
specification.loader.exec_module(runtime)


class RuntimeInstallationTests(unittest.TestCase):
    def setUp(self):
        pins = patch.object(runtime, 'PINNED_DIGESTS', dict(runtime.PINNED_DIGESTS))
        pins.start()
        self.addCleanup(pins.stop)

    def assets(self, directory, extra=None, executable=True):
        archive = directory / runtime.ARCHIVE
        with zipfile.ZipFile(archive, 'w') as bundle:
            entry = zipfile.ZipInfo('electron')
            entry.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            bundle.writestr(entry, b'unit-test executable fixture, not real Electron')
            bundle.writestr('locales/en-US.pak', b'locale fixture')
            if extra:
                bundle.writestr(*extra)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = directory / 'SHASUMS256.txt'
        manifest.write_text(f'{digest} *{runtime.ARCHIVE}\n')
        runtime.PINNED_DIGESTS.update({runtime.ARCHIVE: digest,
                                     runtime.MANIFEST: hashlib.sha256(manifest.read_bytes()).hexdigest()})
        return archive, manifest, directory / 'installed'

    def test_verified_archive_installs_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest, destination = self.assets(Path(temporary))
            result = runtime.install(archive, manifest, destination)
            self.assertTrue(os.access(destination / 'electron', os.X_OK))
            self.assertEqual((destination / 'locales/en-US.pak').read_bytes(), b'locale fixture')
            self.assertEqual(result['archive_sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(json.loads((destination / 'runtime-provenance.json').read_text()), result)
            self.assertEqual((destination / 'SHASUMS256.txt').read_bytes(), manifest.read_bytes())
            with self.assertRaises(FileExistsError):
                runtime.install(archive, manifest, destination)

    def test_digest_mismatch_never_extracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest, destination = self.assets(Path(temporary))
            with archive.open('ab') as output:
                output.write(b'tampered')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                runtime.install(archive, manifest, destination)
            self.assertFalse(destination.exists())

    def test_manifest_requires_exact_version_platform_and_unique_digest(self):
        checksum = 'a' * 64
        for text in ['', f'{checksum} electron-v6.0.0-linux-x64.zip\n',
                     f'{checksum} {runtime.ARCHIVE}\n' * 2, f'123 {runtime.ARCHIVE}']:
            with self.subTest(manifest=text), self.assertRaises(ValueError):
                runtime.expected_digest(text)

    def test_replacing_archive_and_manifest_cannot_replace_pinned_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest, destination = self.assets(Path(temporary))
            archive.write_bytes(b'another release')
            manifest.write_text(f'{hashlib.sha256(archive.read_bytes()).hexdigest()} *{runtime.ARCHIVE}\n')
            with self.assertRaisesRegex(ValueError, 'manifest SHA256 mismatch'):
                runtime.install(archive, manifest, destination)
            self.assertFalse(destination.exists())

    def test_archive_traversal_is_rejected_before_extracting(self):
        for name in ['../escape', '/absolute', 'locales/../../escape', '..\\escape']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                archive, manifest, destination = self.assets(Path(temporary), (name, b'unsafe'))
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    runtime.install(archive, manifest, destination)
                self.assertFalse(destination.exists())

    def test_symlink_is_rejected_before_extracting(self):
        entry = zipfile.ZipInfo('link')
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest, destination = self.assets(Path(temporary), (entry, '../outside'))
            with self.assertRaisesRegex(ValueError, 'symlink'):
                runtime.install(archive, manifest, destination)
            self.assertFalse(destination.exists())

    def test_missing_executable_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest, destination = self.assets(Path(temporary), executable=False)
            with self.assertRaisesRegex(ValueError, 'executable'):
                runtime.install(archive, manifest, destination)
            self.assertFalse(destination.exists())

    def test_offline_cli_uses_only_provided_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive, manifest, destination = self.assets(directory)
            with patch('sys.argv', ['install-render-runtime.py', '--assets', str(directory),
                                    '--destination', str(destination)]), \
                 patch.object(runtime, 'download', side_effect=AssertionError('unexpected network')):
                runtime.main()
            self.assertEqual(json.loads((destination / 'runtime-provenance.json').read_text())['electron_version'], '9.2.1')


if __name__ == '__main__':
    unittest.main()
