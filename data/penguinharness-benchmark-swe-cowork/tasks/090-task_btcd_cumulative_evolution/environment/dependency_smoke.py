#!/usr/bin/env python3
"""Check transitive metadata hydration using real Go and a local-only proxy."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import zipfile

from prefetch_workspaces import prepare


def run(go="go"):
    with tempfile.TemporaryDirectory(prefix="dependency-smoke-", dir=os.environ.get("TMPDIR")) as temporary:
        base = Path(temporary).resolve()
        proxy = base / "proxy"
        dependencies = {
            ("leaf", "v1.0.0"): ("", "package leaf\nfunc Value() int { return 1 }\n"),
            ("leaf", "v1.1.0"): ("", "package leaf\nfunc Value() int { return 42 }\n"),
            ("leaf", "v1.2.0"): ("", "package leaf\nfunc Value() int { return 2 }\n"),
            ("leaf", "v1.3.0"): ("", "package leaf\nfunc Value() int { return 84 }\n"),
            ("bridge", "v1.0.0"): (
                "require example.org/leaf v1.0.0\n",
                'package bridge\nimport "example.org/leaf"\nfunc Value() int { return leaf.Value() }\n'),
            ("bridge", "v1.1.0"): (
                "require example.org/leaf v1.2.0\n",
                'package bridge\nimport "example.org/leaf"\nfunc Value() int { return leaf.Value() }\n'),
        }
        for (name, version), (requirements, source) in dependencies.items():
            module = "example.org/" + name
            manifest = f"module {module}\ngo 1.16\n{requirements}"
            directory = proxy / module / "@v"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (version + ".mod")).write_text(manifest)
            (directory / (version + ".info")).write_text(json.dumps(
                {"Version": version, "Time": "2020-01-01T00:00:00Z"}))
            with zipfile.ZipFile(directory / (version + ".zip"), "w") as archive:
                archive.writestr(f"{module}@{version}/go.mod", manifest)
                archive.writestr(f"{module}@{version}/{name}.go", source)
        root = base / "manifests/baseline"
        root.mkdir(parents=True)
        (root / "go.mod").write_text("""module example.org/application
go 1.16
require (
    example.org/bridge v1.0.0
    example.org/leaf v1.1.0
)
""")
        (root / "application_test.go").write_text('''package application
import (
    "testing"
    "example.org/bridge"
)
func TestSelectedDependency(test *testing.T) {
    if bridge.Value() != 42 { test.Fatal("wrong selected dependency") }
}
''')
        final = root.parent / "final"
        final.mkdir()
        (final / "go.mod").write_text((root / "go.mod").read_text().replace(
            "example.org/bridge v1.0.0", "example.org/bridge v1.1.0").replace(
            "example.org/leaf v1.1.0", "example.org/leaf v1.3.0"))
        (final / "application_test.go").write_text(
            (root / "application_test.go").read_text().replace("!= 42", "!= 84"))
        environment = {
            "GOPATH": str(base / "gopath"), "GOMODCACHE": str(base / "modules"),
            "GOCACHE": str(base / "build-cache"), "GOTOOLCHAIN": "local",
            "GOSUMDB": "off", "GOPROXY": proxy.as_uri(), "GOTELEMETRY": "off",
            "GOMAXPROCS": "2", "GOFLAGS": "-p=2", "GOWORK": "off",
        }
        manifests = {path: path.read_bytes() for path in root.parent.rglob("go.mod")}
        workspaces = base / "workspaces"

        def execute(arguments, stage="baseline"):
            completed = subprocess.run([go, *arguments], cwd=root.parent / stage, text=True, capture_output=True,
                                       env={**os.environ, "GOWORK": str(workspaces / stage / "go.work"),
                                            "GOPROXY": "off"}, timeout=180)
            print(json.dumps({"command": [go, *arguments], "exit_code": completed.returncode,
                              "stdout": completed.stdout, "stderr": completed.stderr}), flush=True)
            return completed

        with patch.dict(os.environ, environment):
            prepare(base / "manifests", workspaces, go, stage_names=["baseline"])
            try:
                prepare(base / "manifests", workspaces, go, offline=True, stage_names=["final"])
            except subprocess.CalledProcessError:
                print("PASS: baseline-only hydration cannot satisfy a different final graph")
            else:
                raise AssertionError("unhydrated final graph unexpectedly passed offline")
            prepare(base / "manifests", workspaces, go)
            prepare(base / "manifests", workspaces, go, offline=True)
            for stage, version in (("baseline", "v1.0.0"), ("final", "v1.2.0")):
                metadata = base / f"modules/cache/download/example.org/leaf/@v/{version}.mod"
                metadata.unlink()
                incomplete = execute(["list", "-m", "all"], stage)
                assert incomplete.returncode != 0 and "module lookup disabled by GOPROXY=off" in incomplete.stderr
                print(f"PASS: {stage} missing non-selected transitive metadata is an offline graph failure")
            prepare(base / "manifests", workspaces, go)
            proxy.rename(base / "unavailable-proxy")
            prepare(base / "manifests", workspaces, go, offline=True)
            for stage in ("baseline", "final"):
                assert execute(["test", "-p=2", "-count=1", "./..."], stage).returncode == 0
            assert all(path.read_bytes() == content for path, content in manifests.items())
            print("PASS: graph rehydration repairs offline production imports without changing release manifests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", default="go")
    run(parser.parse_args().go)
