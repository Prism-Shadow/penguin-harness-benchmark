#!/usr/bin/env python3
"""Exercise offline source bindings with a real Go toolchain and empty caches."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from module_workspace import create_workspace


def run(go="go"):
    with tempfile.TemporaryDirectory(prefix="workspace-smoke-", dir=os.environ.get("TMPDIR")) as temporary:
        base = Path(temporary).resolve()
        root = base / "source tree"
        root.mkdir()
        fixtures = {
            "go.mod": """module example.org/source
go 1.23.2
require (
    example.org/source/codec v1.1.0
    example.org/source/bridge v1.0.0
)
""",
            "library/library.go": "package library\nfunc Value() int { return 42 }\n",
            "source.go": "package source\n",
            "source_test.go": """package source
import (
    "testing"
    "example.org/source/codec"
    "example.org/source/bridge"
)
func TestSourceBinding(test *testing.T) {
    if codec.Value() != 42 || bridge.Value() != 42 {
        test.Fatal("submitted source was not used")
    }
}
""",
            "codec/go.mod": """module example.org/source/codec
go 1.22
require example.org/source v0.24.2
""",
            "codec/codec.go": """package codec
import "example.org/source/library"
func Value() int { return library.Value() }
""",
            "bridge/go.mod": """module example.org/source/bridge
go 1.22
require example.org/source/codec v1.0.0
""",
            "bridge/bridge.go": """package bridge
import "example.org/source/codec"
func Value() int { return codec.Value() }
""",
        }
        for relative, content in fixtures.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        manifests = {path: path.read_bytes() for path in root.rglob("go.mod")}
        workspace = base / "go.work"
        environment = {
            **os.environ, "GOWORK": str(workspace), "GOPROXY": "off", "GOSUMDB": "off",
            "GOTOOLCHAIN": "local", "GOMAXPROCS": "2", "GOFLAGS": "-p=2",
            "GOPATH": str(base / "gopath"), "GOMODCACHE": str(base / "modules"),
            "GOCACHE": str(base / "build-cache"), "GOTELEMETRY": "off",
        }

        def execute(arguments, directory=root):
            completed = subprocess.run([go, *arguments], cwd=directory, env=environment,
                                       text=True, capture_output=True, timeout=180)
            print(json.dumps({"command": [go, *arguments], "cwd": str(directory),
                              "exit_code": completed.returncode,
                              "stdout": completed.stdout, "stderr": completed.stderr}), flush=True)
            return completed

        modules = create_workspace(root, workspace, go)
        for directory in modules.values():
            assert execute(["test", "-p=2", "-count=1", "./..."], directory).returncode == 0
        assert execute(["list", "-m", "all"]).returncode == 0
        print("PASS: empty-cache offline module graph and all submitted packages")
        (root / "library/library.go").write_text("package library\nfunc Value() int { return 41 }\n")
        mutated = execute(["test", "-p=2", "-count=1", "./..."])
        assert mutated.returncode != 0 and "submitted source was not used" in mutated.stdout
        print("PASS: production source mutation is observed rather than a cached implementation")
        (root / "library/library.go").write_text(fixtures["library/library.go"])
        workspace.write_text(workspace.read_text().split("\nreplace (", 1)[0])
        unbound = execute(["list", "-m", "all"])
        assert unbound.returncode != 0 and "module lookup disabled by GOPROXY=off" in unbound.stderr
        print("PASS: use-only workspace reproduces the missing versioned metadata failure")
        assert all(path.read_bytes() == content for path, content in manifests.items())
        assert not list((base / "modules").rglob("*.mod"))
        assert not list((base / "modules").rglob("*.zip"))
        print("PASS: release manifests unchanged and no downloaded module metadata or source archives")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", default="go")
    run(parser.parse_args().go)
