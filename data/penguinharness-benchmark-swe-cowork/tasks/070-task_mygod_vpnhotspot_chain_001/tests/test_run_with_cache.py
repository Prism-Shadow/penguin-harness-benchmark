import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

import run_with_cache


ROOT = Path(__file__).resolve().parent
CHILD = """
import json
import os
from pathlib import Path
import stat
import sys

root = Path(sys.argv[1])
cache = Path(os.environ['VPNHOTSPOT_RUN_CACHE'])
assert stat.S_IMODE(cache.stat().st_mode) == 0o700
assert stat.S_IMODE((cache / 'tmp').stat().st_mode) == 0o700
assert os.environ['CARGO_BUILD_JOBS'] == '2'
assert os.environ['CARGO_NET_OFFLINE'] == 'true'
for key in ('TMPDIR', 'CARGO_TARGET_DIR', 'VPNHOTSPOT_STABLE_STUB_DIR',
            'VPNHOTSPOT_CARGO_HOME_CACHE', 'CARGO_HOME'):
    path = Path(os.environ[key])
    assert path.parent == cache
    path.mkdir(exist_ok=True)
    (path / 'private-input').write_text('verifier-local build input')
(cache / 'external-link').symlink_to(root / 'unrelated', target_is_directory=True)
(root / 'observed.json').write_text(json.dumps({'cache': str(cache), 'exit': int(sys.argv[2])}))
raise SystemExit(int(sys.argv[2]))
"""


class CacheLifecycleTests(unittest.TestCase):
    def test_command_status_and_exported_evidence_survive_private_cache_cleanup(self):
        for status in (0, 1, 37):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                unrelated = root / "unrelated"
                unrelated.mkdir(mode=0o700)
                sentinel = unrelated / "keep"
                sentinel.write_text("not owned by this run")
                sentinel.chmod(0o600)
                stale_cache = root / "task-cache-other-run"
                stale_cache.mkdir(mode=0o700)
                command = [sys.executable, "-I", "-S", "-B", str(ROOT / "run_with_cache.py"),
                           str(root), sys.executable, "-I", "-S", "-B", "-c", CHILD, str(root), str(status)]
                completed = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(completed.returncode, status, completed.stderr)
                observed = json.loads((root / "observed.json").read_text())
                self.assertEqual(observed["exit"], status)
                self.assertFalse(Path(observed["cache"]).exists())
                self.assertEqual(list(root.glob("task-cache-*")), [stale_cache])
                self.assertEqual(sentinel.read_text(), "not owned by this run")
                self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o700)

    def test_spawn_failure_cleans_only_new_cache_and_preserves_parent_environment(self):
        original_environment = dict(os.environ)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                run_with_cache.run(root, [str(root / "missing-command")])
            self.assertEqual(list(root.iterdir()), [])
        self.assertEqual(dict(os.environ), original_environment)


if __name__ == "__main__":
    unittest.main()
