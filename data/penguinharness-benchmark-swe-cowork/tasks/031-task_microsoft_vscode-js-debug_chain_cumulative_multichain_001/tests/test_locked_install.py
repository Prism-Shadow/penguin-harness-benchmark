import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class LockedInstallTests(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get('TEST_TMPDIR')
        self.assertTrue(scratch, 'Set TEST_TMPDIR on the task data volume')
        self.temporary = tempfile.TemporaryDirectory(prefix='npm-retry-', dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.trace = self.directory / 'trace'
        self.tools = self.directory / 'bin'
        self.tools.mkdir()
        self.logs = self.directory / 'logs'
        self.logs.mkdir()
        self.environment = dict(os.environ, PATH=str(self.tools) + ':' + os.environ['PATH'],
                                RETRY_TRACE=str(self.trace), RETRY_STATE=str(self.directory / 'state'),
                                TMPDIR=str(self.logs), FAILURES='1', FAILURE_CODE='FETCH_ERROR')
        scripts = {
            'npm': '''attempt=0
test ! -f "$RETRY_STATE" || attempt=$(cat "$RETRY_STATE")
attempt=$((attempt + 1))
echo "$attempt" > "$RETRY_STATE"
echo "npm:$*" >> "$RETRY_TRACE"
if [ "$attempt" -le "$FAILURES" ]; then
  echo "npm ERR! code $FAILURE_CODE" >&2
  echo "failure on attempt $attempt" >&2
  exit 23
fi
echo installed
''',
            'sleep': 'echo "sleep:$*" >> "$RETRY_TRACE"\n',
        }
        for name, script in scripts.items():
            executable = self.tools / name
            executable.write_text('#!/bin/sh\n' + script)
            executable.chmod(0o755)

    def install(self, *arguments):
        result = subprocess.run(['sh', str(ROOT / 'environment/install-locked.sh'), *arguments],
                                cwd=self.directory, env=self.environment, text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(list(self.logs.iterdir()), [])
        return result

    def test_success_does_not_retry_and_keeps_locked_command(self):
        self.environment['FAILURES'] = '0'
        result = self.install('--ignore-scripts')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(), 'npm:ci --no-audit --no-fund --ignore-scripts\n')

    def test_transient_timeout_retries_and_preserves_failure_output(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text().splitlines(), [
            'npm:ci --no-audit --no-fund', 'sleep:5', 'npm:ci --no-audit --no-fund'])
        self.assertIn('failure on attempt 1', result.stderr)
        self.assertIn('installed', result.stdout)

    def test_exhausted_network_failure_stays_failure(self):
        self.environment['FAILURES'] = '9'
        result = self.install()
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.trace.read_text().count('npm:ci'), 3)
        self.assertEqual(self.trace.read_text().count('sleep:'), 2)
        for attempt in range(1, 4):
            self.assertIn(f'failure on attempt {attempt}', result.stderr)

    def test_integrity_auth_and_compile_failures_are_not_retried(self):
        for code in ('EINTEGRITY', 'E401', 'EUSAGE', '1'):
            with self.subTest(code=code):
                self.environment['FAILURE_CODE'] = code
                self.environment['FAILURES'] = '9'
                self.trace.unlink(missing_ok=True)
                result = self.install()
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertEqual(self.trace.read_text(), 'npm:ci --no-audit --no-fund\n')
                self.assertNotIn('retrying', result.stderr)


if __name__ == '__main__':
    unittest.main()
