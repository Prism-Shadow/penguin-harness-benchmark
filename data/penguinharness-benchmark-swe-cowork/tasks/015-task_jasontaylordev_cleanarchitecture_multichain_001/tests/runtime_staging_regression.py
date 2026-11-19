"""Load the real entry modules from the installed closure, without source imports."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent


class RuntimeStagingRegression(unittest.TestCase):
    def test_installed_native_and_template_entries_load_and_observe_sqlite(self):
        with tempfile.TemporaryDirectory(prefix='probe-install-') as temporary:
            destination = Path(temporary) / 'environment'
            command = [sys.executable, str(ROOT / 'stage_runtime.py'), '--source',
                       str(ROOT / 'private-runtime/task-environment'), '--destination', str(destination)]
            for _ in range(2):
                subprocess.run(command, check=True, capture_output=True, text=True)
            script = '''import gc, sqlite3
from pathlib import Path
import native_suite, template_probe
gc.disable()
store = Path('observed.db')
writer = sqlite3.connect(store)
writer.execute('PRAGMA journal_mode=WAL')
writer.execute('CREATE TABLE InstalledProbe(Id integer)')
writer.commit()
writer.close()
for probe in (native_suite, template_probe):
    assert probe.table_names(store) == {'InstalledProbe'}
with sqlite3.connect(store, timeout=0) as check:
    assert check.execute('PRAGMA journal_mode=DELETE').fetchone()[0] == 'delete'
print('PASS installed native/template entry imports and SQLite lock release')
'''
            environment = dict(os.environ, PYTHONPATH=str(destination), PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([sys.executable, '-c', script], cwd=temporary,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS installed native/template', result.stdout)


if __name__ == '__main__':
    unittest.main()
