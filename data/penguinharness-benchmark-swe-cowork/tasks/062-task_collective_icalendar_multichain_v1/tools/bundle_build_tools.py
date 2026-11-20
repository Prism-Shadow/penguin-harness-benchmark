"""Package only task-owned asset preparation code for the environment context."""

import argparse
import gzip
import io
from pathlib import Path
import tarfile


FILES = (
    "environment/regression_assets.py",
    "tools/acquire_regression_assets.py",
    "tools/archive_regression_assets.py",
    "tools/frozen_regression.py",
    "tools/materialize_regression.py",
    "tools/rebuild_repository.py",
    "tools/restore_regression_assets.py",
)


def bundle(root):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name in FILES:
                path = root / name
                if path.is_symlink():
                    raise ValueError(f"Symlinked build helper: {name}")
                content = path.read_bytes()
                member = tarfile.TarInfo(name)
                member.mode = 0o644
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
    return output.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "environment/build-tools.tar.gz"
    content = bundle(root)
    if arguments.check:
        if destination.read_bytes() != content:
            raise SystemExit("Stale build tools; regenerate with tools/bundle_build_tools.py")
        print("Build helper bundle matches the seven allowlisted sources exactly.")
    else:
        destination.write_bytes(content)
