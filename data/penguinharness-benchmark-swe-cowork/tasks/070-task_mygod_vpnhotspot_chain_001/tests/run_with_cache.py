"""Keep verifier build inputs private and out of exported artifacts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(log_root, command):
    with tempfile.TemporaryDirectory(prefix="task-cache-", dir=log_root) as temporary:
        cache = Path(temporary)
        (cache / "tmp").mkdir(mode=0o700)
        environment = dict(os.environ)
        environment.update(
            VPNHOTSPOT_RUN_CACHE=str(cache),
            TMPDIR=str(cache / "tmp"),
            CARGO_TARGET_DIR=str(cache / "target"),
            VPNHOTSPOT_STABLE_STUB_DIR=str(cache / "stubs"),
            VPNHOTSPOT_CARGO_HOME_CACHE=str(cache / "cargo-home"),
            CARGO_HOME=str(cache / "cargo-home"),
            CARGO_BUILD_JOBS="2",
            CARGO_NET_OFFLINE="true",
        )
        return subprocess.run(command, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]).resolve(), sys.argv[2:]))
