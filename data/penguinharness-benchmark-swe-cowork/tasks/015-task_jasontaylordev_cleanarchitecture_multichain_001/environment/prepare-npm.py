#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path


CLIENTS = ("src/Web/ClientApp", "src/Web/ClientApp-React")
LEGACY_REACT_BASELINE = (
    "src/Web/ClientApp-React",
    "b8a98a9a018c23bb682b23c1e067e4c9c12948a7f83163c74d9d21d0804076dc",
    "7453101c420d45d334b4e1d0255a2b86fae6f163d0ee0cd1296110be80a3802c",
)
TRANSIENT_NETWORK_ERROR = re.compile(
    r"^npm (?:error|ERR!) code (?:ETIMEDOUT|ESOCKETTIMEDOUT|ECONNRESET|"
    r"ECONNREFUSED|EAI_AGAIN|ENETUNREACH|E502|E503|E504)\s*$", re.MULTILINE)
NPM_ERROR_CODE = re.compile(r"^npm (?:error|ERR!) code \S+\s*$", re.MULTILINE)


def output_text(output: str | bytes | None) -> str:
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


def run_npm(command: list[str], *, cwd: Path, online: bool) -> None:
    attempts = 3 if online and "--offline" not in command else 1
    environment = os.environ.copy()
    if attempts > 1 and not any(key.lower() == "npm_config_loglevel" for key in environment):
        environment["npm_config_loglevel"] = "verbose"
    for attempt in range(1, attempts + 1):
        print(f"npm attempt {attempt}/{attempts} in {cwd}: {json.dumps(command)}", flush=True)
        try:
            result = subprocess.run(command, cwd=cwd, check=False, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
                                    env=environment)
        except subprocess.TimeoutExpired as error:
            output = output_text(error.stdout)
            print(output, end="", flush=True)
            print(f"\nnpm terminal_state=timed_out timeout_seconds={error.timeout}", flush=True)
            if attempt == attempts or any(not TRANSIENT_NETWORK_ERROR.fullmatch(code)
                                          for code in NPM_ERROR_CODE.findall(output)):
                raise
            reason = "npm process deadline (cause undetermined)"
        else:
            output = output_text(result.stdout)
            print(output, end="", flush=True)
            print(f"\nnpm terminal_state=exited return_code={result.returncode}", flush=True)
            if result.returncode == 0:
                return
            codes = NPM_ERROR_CODE.findall(output)
            if attempt == attempts or not codes or any(not TRANSIENT_NETWORK_ERROR.fullmatch(code) for code in codes):
                raise subprocess.CalledProcessError(result.returncode, command, output=output)
            reason = "Transient npm network failure"
        delay = 5 * attempt
        print(f"{reason}; retrying the same command in {delay}s", flush=True)
        time.sleep(delay)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def baseline_install_arguments(relative: str, manifest: bytes, lock: bytes) -> list[str]:
    if (relative, digest(manifest), digest(lock)) == LEGACY_REACT_BASELINE:
        return ["--legacy-peer-deps"]
    return []


def validate_repair(original: dict, repaired: dict) -> None:
    if original.get("lockfileVersion") != repaired.get("lockfileVersion"):
        raise ValueError("lock format changed during dependency preparation")
    old_packages = original["packages"]
    new_packages = repaired["packages"]
    if old_packages[""] != new_packages.get(""):
        raise ValueError("root manifest changed during dependency preparation")
    for name, package in old_packages.items():
        replacement = new_packages.get(name)
        if replacement is None:
            raise ValueError(f"locked package removed: {name}")
        for field in ("version", "resolved", "integrity", "dependencies", "peerDependencies",
                      "peerDependenciesMeta", "optionalDependencies", "link"):
            if package.get(field) != replacement.get(field):
                raise ValueError(f"locked package changed: {name}: {field}")


def prepare(repository: Path, artifacts: Path, *, warm: bool) -> None:
    catalog = Path("/opt/frontend-closures")
    if not warm and catalog.is_dir():
        specification = importlib.util.spec_from_file_location("frontend_closure", Path(__file__).with_name("frontend-closure.py"))
        closure = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(closure)
        if closure.select(repository, catalog) is not None:
            closure.activate(repository, catalog, Path(os.environ.get("FRONTEND_CLOSURE_WORKSPACE", "/data2/frontend-views")))
            return
    for relative in CLIENTS:
        client = repository / relative
        manifest = (client / "package.json").read_bytes()
        lock_path = client / "package-lock.json"
        original = lock_path.read_bytes()
        artifact = artifacts / client.name
        if warm:
            install_arguments = baseline_install_arguments(relative, manifest, original)
            if not install_arguments:
                run_npm(["npm", "install", "--package-lock-only", "--ignore-scripts",
                         "--no-audit", "--no-fund"], cwd=client, online=True)
            else:
                print("Retaining frozen React baseline lock and its legacy peer graph", flush=True)
            repaired = lock_path.read_bytes()
            if (client / "package.json").read_bytes() != manifest:
                raise ValueError(f"npm changed the baseline manifest: {relative}")
            validate_repair(json.loads(original), json.loads(repaired))
            run_npm(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", *install_arguments],
                    cwd=client, online=True)
            artifact.mkdir(parents=True, exist_ok=True)
            (artifact / "package-lock.json").write_bytes(repaired)
            receipt = {"manifest_sha256": digest(manifest), "original_lock_sha256": digest(original),
                       "prepared_lock_sha256": digest(repaired), "install_arguments": install_arguments}
            (artifact / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(f"Prepared baseline lock: {relative}: {json.dumps(receipt)}", flush=True)
        else:
            receipt = json.loads((artifact / "receipt.json").read_text())
            if digest(manifest) == receipt["manifest_sha256"] and digest(original) in (
                    receipt["original_lock_sha256"], receipt["prepared_lock_sha256"]):
                repaired = (artifact / "package-lock.json").read_bytes()
                if digest(repaired) != receipt["prepared_lock_sha256"]:
                    raise ValueError(f"prepared lock integrity mismatch: {relative}")
                validate_repair(json.loads(original), json.loads(repaired))
                lock_path.write_bytes(repaired)
                print(f"Restored prepared baseline lock: {relative}", flush=True)
            else:
                print(f"Preserving solver dependency changes: {relative}", flush=True)
            install_arguments = baseline_install_arguments(relative, manifest, lock_path.read_bytes())
            run_npm(["npm", "ci", "--offline", "--ignore-scripts", "--no-audit", "--no-fund",
                     *install_arguments],
                    cwd=client, online=False)


def resolve_offline_locks(repository: Path) -> None:
    for relative in CLIENTS:
        client = repository / relative
        manifest_path = client / "package.json"
        manifest = manifest_path.read_bytes()
        package = json.loads(manifest)
        lock_path = client / "package-lock.json"
        original_lock = lock_path.read_bytes() if lock_path.exists() else None
        fields = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies", "overrides")
        with tempfile.TemporaryDirectory(prefix=".solution-lock-") as folder:
            staging = Path(folder)
            (staging / "package.json").write_bytes(manifest)
            if original_lock is not None:
                root = json.loads(original_lock).get("packages", {}).get("")
                if root is not None and all(root.get(field, {}) == package.get(field, {}) for field in fields):
                    (staging / "package-lock.json").write_bytes(original_lock)
                else:
                    print(f"Ignoring stale solution lock for changed manifest: {relative}", flush=True)
            run_npm(["npm", "install", "--package-lock-only", "--offline", "--ignore-scripts",
                     "--no-audit", "--no-fund"], cwd=staging, online=False)
            if (staging / "package.json").read_bytes() != manifest or manifest_path.read_bytes() != manifest:
                raise ValueError(f"manifest changed during offline lock resolution: {relative}")
            generated = staging / "package-lock.json"
            if not generated.is_file():
                raise ValueError(f"offline resolution produced no lock: {relative}")
            lock = generated.read_bytes()
            root = json.loads(lock)["packages"][""]
            for field in fields[:4]:
                if root.get(field, {}) != package.get(field, {}):
                    raise ValueError(f"resolved lock does not match manifest: {relative}: {field}")
            if (lock_path.read_bytes() if lock_path.exists() else None) != original_lock:
                raise ValueError(f"solution lock changed during offline resolution: {relative}")
            lock_path.write_bytes(lock)
        print(f"Resolved offline solution lock: {relative}: {digest(lock)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--repository", type=Path, default=Path(os.environ.get("REPO_DIR", "/app/code")))
    parser.add_argument("--artifacts", type=Path, default=Path("/opt/offline-baseline-locks"))
    parser.add_argument("--retry-online", action="store_true")
    parser.add_argument("--resolve-offline-locks", action="store_true")
    parser.add_argument("npm_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.resolve_offline_locks:
        if args.warm or args.retry_online or args.npm_arguments:
            parser.error("--resolve-offline-locks cannot be combined with other preparation modes")
        resolve_offline_locks(args.repository)
        return
    if args.retry_online:
        command = args.npm_arguments
        if command[:1] == ["--"]:
            command = command[1:]
        if not command or args.warm:
            parser.error("--retry-online requires an npm command and cannot be combined with --warm")
        run_npm(["npm", *command], cwd=Path.cwd(), online=True)
        return
    if args.npm_arguments:
        parser.error("unexpected npm arguments without --retry-online")
    prepare(args.repository, args.artifacts, warm=args.warm)


if __name__ == "__main__":
    main()
