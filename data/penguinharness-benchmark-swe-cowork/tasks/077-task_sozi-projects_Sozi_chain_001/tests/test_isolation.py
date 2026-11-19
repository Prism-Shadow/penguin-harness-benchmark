import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile


specification = importlib.util.spec_from_file_location('isolation_audit', Path(__file__).resolve().parents[1] / 'maintenance/isolation-audit.py')
isolation = importlib.util.module_from_spec(specification)
specification.loader.exec_module(isolation)


class IsolationTests(unittest.TestCase):
    def test_forbidden_vendored_source_and_archive_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = b'forbidden later target source fixture'
            forbidden = {hashlib.sha256(payload).hexdigest(): 'future target package'}
            vendored = root / 'pip/_vendor/target/source.py'
            vendored.parent.mkdir(parents=True)
            vendored.write_bytes(payload)
            with zipfile.ZipFile(root / 'target.whl', 'w') as archive:
                archive.writestr('target/source.py', payload)
            with tarfile.open(root / 'target.tgz', 'w:gz') as archive:
                member = tarfile.TarInfo('package/source.js')
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            records, violations, errors = isolation.audit([root], forbidden)
            self.assertFalse(errors)
            self.assertEqual(len(violations), 3)
            self.assertTrue(any('!target/source.py' in record['path'] for record in records))

    def test_missing_roots_and_external_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'outside').symlink_to(root.parent / 'unscanned')
            records, violations, errors = isolation.audit([root, root / 'missing'], {})
            self.assertEqual(len(errors), 2)
            self.assertFalse(violations)


if __name__ == '__main__':
    unittest.main()
