import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run


class PreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.electron = self.root / 'electron'
        self.electron.touch(mode=0o700)
        for replacement in [patch.dict(os.environ, SOZI_ELECTRON=str(self.electron)),
                            patch.object(run.shutil, 'which', return_value='/available')]:
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_bridge_is_prepared_before_real_renderer_check(self):
        commands = []

        def prepare(command, **options):
            commands.append(command)
            self.assertTrue(options['check'])
            self.assertEqual(options['cwd'], self.root)

        def electron(command, log, **options):
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[1][1], str(run.ROOT / 'dependencies.cjs'))
            self.assertEqual(commands[1][2], str(self.root))
            self.assertEqual(commands[1][3], options['env']['SOZI_PREFLIGHT_DIR'])
            self.assertEqual(command[-1], str(run.ROOT / 'preflight.cjs'))
            self.assertEqual(command[2], str(self.electron))
            return subprocess.CompletedProcess(command, 0)

        with patch.object(run.subprocess, 'run', side_effect=prepare), patch.object(run, 'run_logged', side_effect=electron) as renderer:
            run.preflight(self.root)
        self.assertEqual(renderer.call_count, 1)

    def test_missing_bridge_input_stops_before_rendering(self):
        failure = subprocess.CalledProcessError(1, ['node', 'dependencies.cjs'])
        with patch.object(run.subprocess, 'run', side_effect=[None, failure]), patch.object(run, 'run_logged') as renderer:
            with self.assertRaises(subprocess.CalledProcessError):
                run.preflight(self.root)
        renderer.assert_not_called()

    def test_renderer_dependency_load_error_is_not_preflight_success(self):
        with patch.object(run.subprocess, 'run'), patch.object(run, 'run_logged', return_value=subprocess.CompletedProcess(['electron'], 2)):
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                run.preflight(self.root)
        self.assertEqual(failure.exception.returncode, 2)


if __name__ == '__main__':
    unittest.main()
