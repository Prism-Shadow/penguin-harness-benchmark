"""Packaging tests with small archive fixtures, not a native Ada test substitute."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


SOURCE = Path(__file__).resolve().parents[1] / 'environment/install_test_dependencies.py'
SPEC = importlib.util.spec_from_file_location('ada_dependency_installer', SOURCE)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)
PACKAGES = [('googletest', '1.15.2', 'google/googletest'),
            ('simdjson', '3.10.1', 'simdjson/simdjson')]


def archive_bytes(prefix, path='CMakeLists.txt', link=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        entry = tarfile.TarInfo(prefix + '/' + path)
        if link is None:
            contents = b'fixture for installer testing only\n'
            entry.size = len(contents)
            archive.addfile(entry, io.BytesIO(contents))
        else:
            entry.type = tarfile.SYMTYPE
            entry.linkname = link
            archive.addfile(entry)
    return output.getvalue()


class DependencyInstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='ada-installer-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'deps'
        self.archives = [archive_bytes(f'{name}-{version}')
                         for name, version, repository in PACKAGES]

    def install(self, digests=None, archives=None):
        args = [str(SOURCE), '--root', str(self.root)]
        if digests is not None:
            args += [f'--{name}-sha256={digest}'
                     for (name, version, repository), digest in zip(PACKAGES, digests)]
        responses = [io.BytesIO(data) for data in (archives or self.archives)]
        with patch.object(sys, 'argv', args), patch.object(
                INSTALLER.urllib.request, 'urlopen', side_effect=responses) as fetch:
            INSTALLER.main()
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [
            f'https://codeload.github.com/{repository}/tar.gz/refs/tags/v{version}'
            for name, version, repository in PACKAGES])
        return json.loads((self.root / 'manifest.json').read_text())

    def test_default_build_records_version_pins_without_claiming_approval(self):
        manifest = self.install()
        for record, data, (name, version, repository) in zip(manifest, self.archives, PACKAGES):
            self.assertEqual(record['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(record['version'], version)
            self.assertIsNone(record['expected_sha256'])
            self.assertEqual(record['integrity'], 'version-pinned-tls')
            self.assertEqual((self.root / name / 'CMakeLists.txt').read_bytes(),
                             b'fixture for installer testing only\n')
            self.assertFalse((self.root / f'{name}.tar.gz').exists())

    def test_supplied_checksums_are_verified(self):
        digests = [hashlib.sha256(data).hexdigest() for data in self.archives]
        manifest = self.install(digests)
        self.assertEqual([record['expected_sha256'] for record in manifest], digests)
        self.assertTrue(all(record['integrity'] == 'checksum-verified' for record in manifest))

    def test_empty_docker_build_arguments_use_the_fixed_versions(self):
        manifest = self.install(['', ''])
        self.assertTrue(all(record['expected_sha256'] is None for record in manifest))

    def test_checksum_mismatch_fails_before_extraction(self):
        with self.assertRaisesRegex(ValueError, 'googletest SHA256 mismatch'):
            self.install(['0' * 64, '0' * 64])
        self.assertFalse((self.root / 'googletest').exists())
        self.assertFalse((self.root / 'manifest.json').exists())

    def test_malformed_checksum_does_not_download(self):
        with patch.object(INSTALLER.urllib.request, 'urlopen') as fetch, patch.object(
                sys, 'argv', [str(SOURCE), '--googletest-sha256=bad', '--root', str(self.root)]):
            with self.assertRaises(SystemExit) as error:
                INSTALLER.main()
        self.assertEqual(error.exception.code, 2)
        fetch.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_unsafe_archives_are_rejected(self):
        for name, data in [
                ('traversal', archive_bytes('googletest-1.15.2', '../escaped')),
                ('version', archive_bytes('googletest-99.0')),
                ('symlink', archive_bytes('googletest-1.15.2', link='/outside'))]:
            with self.subTest(name=name):
                self.root = Path(self.directory.name) / name
                with self.assertRaises(ValueError):
                    self.install(archives=[data, self.archives[1]])
                self.assertFalse((self.root / 'manifest.json').exists())

    def test_download_failure_is_not_a_successful_install(self):
        with patch.object(INSTALLER.urllib.request, 'urlopen', side_effect=URLError('offline')):
            with patch.object(sys, 'argv', [str(SOURCE), '--root', str(self.root)]):
                with self.assertRaises(URLError):
                    INSTALLER.main()
        self.assertFalse((self.root / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
