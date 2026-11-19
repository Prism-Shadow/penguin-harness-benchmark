import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


spec = importlib.util.spec_from_file_location('run_browser', Path(__file__).with_name('run_browser.py'))
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


class BrowserTemporaryDirectoryTests(unittest.TestCase):
    def test_missing_parent_is_created_and_child_is_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'native-container' / 'data2'
            with self.assertRaises(FileNotFoundError):
                with tempfile.TemporaryDirectory(prefix='msr-browser-', dir=root):
                    self.fail('The previous allocator must reject an absent parent')
            with browser.browser_temporary_directory(root) as temporary:
                child = Path(temporary)
                self.assertEqual(child.parent, root)
                self.assertTrue(child.name.startswith('msr-browser-'))
                (child / 'browser-output').write_text('temporary browser data')
            self.assertFalse(child.exists())
            self.assertTrue(root.is_dir())

    def test_existing_parent_and_other_runs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'existing-evidence'
            marker.write_text('retain')
            with browser.browser_temporary_directory(root) as first:
                with browser.browser_temporary_directory(root) as second:
                    self.assertNotEqual(first, second)
                    self.assertTrue(Path(first).is_dir())
                    self.assertTrue(Path(second).is_dir())
                self.assertFalse(Path(second).exists())
                self.assertTrue(Path(first).is_dir())
            self.assertFalse(Path(first).exists())
            self.assertEqual(marker.read_text(), 'retain')

    def test_exception_cleans_only_temporary_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'data2'
            with self.assertRaisesRegex(RuntimeError, 'browser subprocess failed'):
                with browser.browser_temporary_directory(root) as temporary:
                    child = Path(temporary)
                    raise RuntimeError('browser subprocess failed')
            self.assertFalse(child.exists())
            self.assertTrue(root.is_dir())

    def test_invalid_parent_remains_an_os_setup_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'data2'
            root.write_text('not a directory')
            with self.assertRaises(FileExistsError):
                browser.browser_temporary_directory(root)
            self.assertEqual(root.read_text(), 'not a directory')


class ReleaseArchiveTests(unittest.TestCase):
    def test_public_zip_preserves_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'release.zip'
            content = '# [17.4.8]\n\n### Fixed\n- packaged content\n'
            with zipfile.ZipFile(archive, 'w') as release:
                release.writestr('manifest.json', json.dumps({'manifest_version': 3}))
                release.writestr('CHANGELOG.md', content)
            extension = browser.unpack_release(archive, root / 'unpacked')
            self.assertEqual((extension / 'CHANGELOG.md').read_text(), content)

    def test_archive_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as release:
                release.writestr('../escaped.txt', 'bad artifact')
            with self.assertRaisesRegex(ValueError, 'escapes'):
                browser.unpack_release(archive, root / 'unpacked')
            self.assertFalse((root / 'escaped.txt').exists())

    def test_packaged_changelog_cannot_be_an_external_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as release:
                entry = zipfile.ZipInfo('CHANGELOG.md')
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
                release.writestr(entry, '../CHANGELOG.md')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                browser.unpack_release(archive, root / 'unpacked')


if __name__ == '__main__':
    unittest.main()
