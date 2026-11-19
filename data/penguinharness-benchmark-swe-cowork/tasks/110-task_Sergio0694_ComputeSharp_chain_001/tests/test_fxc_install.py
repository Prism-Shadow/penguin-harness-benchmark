import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'environment/native-runtime'))
spec = importlib.util.spec_from_file_location('fxc_install', ROOT / 'environment/native-runtime/install_fxc.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def pe_fixture(machine=0x8664):
    payload = bytearray(128)
    payload[:2] = b'MZ'
    struct.pack_into('<I', payload, 60, 64)
    payload[64:68] = b'PE\0\0'
    struct.pack_into('<H', payload, 68, machine)
    struct.pack_into('<H', payload, 86, 0x2000)
    struct.pack_into('<H', payload, 88, 0x20b)
    return payload


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='fxc-installer-test-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.recipe = self.root / 'winetricks'
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.archive = self.cache / installer.ARCHIVE_NAME
        self.prefix = self.root / 'prefix'
        self.target = self.prefix / 'drive_c/windows/system32/d3dcompiler_47.dll'
        self.target.parent.mkdir(parents=True)
        self.payload = pe_fixture()
        self.write_archive(self.payload)
        self.recipe_line = 'w_download "{}" {} "{}"'.format(
            installer.ARCHIVE_URL, installer.sha256(self.archive), installer.ARCHIVE_NAME)
        self.recipe.write_text('load_d3dcompiler_47()\n{\n    ' + self.recipe_line + '\n}\n')
        self.pin = patch.object(installer, 'RECIPE_SHA256', installer.sha256(self.recipe))
        self.pin.start()
        self.addCleanup(self.pin.stop)
        self.environment = patch.dict(os.environ, WINEARCH='win64')
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write_archive(self, payload):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('core/d3dcompiler_47.dll', payload)

    def fixture_extractor(self, command, **options):
        self.assertEqual(command[:3], ['7z', 'x', '-y'])
        self.assertEqual(command[-1], 'core/d3dcompiler_47.dll')
        self.assertTrue(options['check'])
        self.assertEqual(options['timeout'], 120)
        output = Path(command[4][2:])
        (output / 'core').mkdir()
        with zipfile.ZipFile(command[3]) as archive:
            (output / 'core/d3dcompiler_47.dll').write_bytes(archive.read(command[-1]))
        return subprocess.CompletedProcess(command, 0)

    def install(self):
        return installer.install(self.recipe, self.cache, self.prefix)

    def test_verified_cache_installs_only_x64_without_download_or_registry(self):
        with patch.object(installer, 'download') as fetch, patch.object(
                installer.subprocess, 'run', side_effect=self.fixture_extractor) as commands:
            receipt = self.install()
            self.assertEqual(self.target.read_bytes(), self.payload)
            self.target.write_bytes(b'changed prefix state')
            self.assertEqual(self.install(), receipt)
        fetch.assert_not_called()
        self.assertEqual(commands.call_count, 2)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(receipt['architecture'], 'AMD64')
        self.assertEqual(receipt['dll_sha256'], hashlib.sha256(self.payload).hexdigest())
        self.assertFalse((self.prefix / 'drive_c/windows/syswow64').exists())

    def test_recipe_mutation_is_rejected_before_download_or_extraction(self):
        self.recipe.write_text(self.recipe.read_text() + '\nchanged\n')
        with patch.object(installer, 'download') as fetch, patch.object(installer.subprocess, 'run') as extract:
            with self.assertRaisesRegex(ValueError, 'recipe SHA256 mismatch'):
                self.install()
        fetch.assert_not_called()
        extract.assert_not_called()

    def test_missing_duplicate_or_changed_declarations_fail_closed(self):
        for content in ('', self.recipe_line + '\n' + self.recipe_line,
                        self.recipe_line.replace('win64', 'win32'),
                        self.recipe_line.replace(installer.sha256(self.archive), 'not-a-digest')):
            with self.subTest(content=content):
                self.recipe.write_text(content)
                with patch.object(installer, 'RECIPE_SHA256', installer.sha256(self.recipe)):
                    with self.assertRaises(ValueError):
                        installer.archive_digest(self.recipe)

    def test_continued_and_indented_declaration_reads_same_digest(self):
        self.recipe.write_text('    ' + self.recipe_line.replace(' ', ' \\\n        ', 1))
        with patch.object(installer, 'RECIPE_SHA256', installer.sha256(self.recipe)):
            self.assertEqual(installer.archive_digest(self.recipe), installer.sha256(self.archive))

    def test_corrupt_cached_archive_is_rejected_before_extraction(self):
        self.archive.write_bytes(b'corrupt cached input')
        self.target.write_bytes(b'previous compiler')
        with patch.object(installer, 'download') as fetch, patch.object(installer.subprocess, 'run') as extract:
            with self.assertRaisesRegex(ValueError, 'archive SHA256 mismatch'):
                self.install()
        fetch.assert_not_called()
        extract.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'previous compiler')

    def test_downloaded_archive_is_verified_before_use(self):
        source = self.root / 'source.zip'
        self.archive.rename(source)

        def fetch(program, arguments, urls):
            self.assertEqual(program, 'wget')
            self.assertEqual(arguments[-1], installer.ARCHIVE_URL)
            self.assertTrue(all('/win64/' in url for url in urls))
            shutil.copyfile(source, arguments[1])
            return 0

        with patch.object(installer, 'download', side_effect=fetch) as download, patch.object(
                installer.subprocess, 'run', side_effect=self.fixture_extractor):
            self.install()
        download.assert_called_once()
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_download_success_does_not_bypass_checksum(self):
        self.archive.unlink()

        def fetch(*arguments):
            self.archive.write_bytes(b'nonempty but untrusted')
            return 0

        with patch.object(installer, 'download', side_effect=fetch), patch.object(installer.subprocess, 'run') as extract:
            with self.assertRaisesRegex(ValueError, 'archive SHA256 mismatch'):
                self.install()
        extract.assert_not_called()

    def test_transport_failure_does_not_extract_or_install(self):
        self.archive.unlink()
        with patch.object(installer, 'download', return_value=86), patch.object(installer.subprocess, 'run') as extract:
            with self.assertRaisesRegex(RuntimeError, 'download failed'):
                self.install()
        extract.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_wrong_architecture_and_truncated_images_are_rejected(self):
        path = self.root / 'compiler.dll'
        for payload in (b'not a DLL', pe_fixture(0x14c), pe_fixture()[:80]):
            with self.subTest(payload=payload[:4]):
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    installer.validate_x64_dll(path)

    def test_extraction_failure_preserves_previous_compiler(self):
        self.target.write_bytes(b'previous compiler')
        with patch.object(installer.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, '7z')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.install()
        self.assertEqual(self.target.read_bytes(), b'previous compiler')
        self.assertEqual(list(self.root.glob('fxc-extract-*')), [])

    def test_wrong_prefix_architecture_is_rejected_before_any_commands(self):
        with patch.dict(os.environ, WINEARCH='win32'), patch.object(installer.subprocess, 'run') as commands:
            with self.assertRaisesRegex(ValueError, 'WINEARCH=win64'):
                self.install()
        commands.assert_not_called()


class InstalledRecipeTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/bin/winetricks').is_file(),
                         'the pinned Debian recipe is only available in the rebuilt image')
    def test_actual_pinned_recipe_supplies_the_win64_digest(self):
        self.assertRegex(installer.archive_digest(Path('/usr/bin/winetricks')), '^[0-9a-f]{64}$')


if __name__ == '__main__':
    unittest.main()
