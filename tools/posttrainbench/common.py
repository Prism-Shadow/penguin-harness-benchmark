"""Shared, dependency-free PostTrainBench integration contracts (Python 3.11+ host)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ID = "penguinharness-benchmark-posttrainbench"
# RFC-0001 keeps the repository a package index: the catalog (24 cells + the launch template)
# lives with the tooling that consumes it, and the package holds the task descriptions.
CATALOG = ROOT / "tools" / "posttrainbench" / "catalog"
PACKAGE = ROOT / "packages" / BENCHMARK_ID
UPSTREAM_COMMIT = "76837fc3bfc2c87870638861ce0a55db5c7a49d3"
HARBOR_VERSION = "0.23.0"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def upstream_check(path: Path) -> Path:
    path = path.resolve()
    head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if head != UPSTREAM_COMMIT:
        raise ValueError(f"PostTrainBench must be at {UPSTREAM_COMMIT}; got {head}")
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True)
    if dirty:
        raise ValueError("PostTrainBench has tracked edits; use a clean pinned checkout")
    return path


def catalog() -> dict:
    return read_json(CATALOG / "manifest.json")


def file_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*"))
            if p.is_file() and p.name != "prepared.json" and "__pycache__" not in p.parts}


def validate_prepared(root: Path) -> dict:
    lock = read_json(root / "prepared.json")
    if lock.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ValueError("Prepared tasks have a different upstream version; prepare again")
    if file_hashes(root) != lock.get("files"):
        raise ValueError("Prepared task files changed or are missing; prepare again in a new directory")
    return lock
