from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER = shutil.which('x86_64-w64-mingw32-g++')


@unittest.skipUnless(COMPILER, 'MinGW is unavailable; PE compilation requires the rebuilt image')
class WorkerBuildTests(unittest.TestCase):
    def test_production_worker_cross_compiles_and_links(self):
        with tempfile.TemporaryDirectory(prefix='fxc-worker-build-') as scratch:
            result = subprocess.run(
                [COMPILER, '-std=c++17', '-O2', '-static', '-Wall', '-Wextra',
                 '-o', str(Path(scratch) / 'compiler.exe'),
                 str(ROOT / 'environment/native-runtime/fxc_worker.cpp')],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
