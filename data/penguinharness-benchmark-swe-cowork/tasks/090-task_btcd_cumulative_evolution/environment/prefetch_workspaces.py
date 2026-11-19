#!/usr/bin/env python3
"""Materialize the same module graphs used by the offline verifier."""
import argparse
import os
from pathlib import Path
import subprocess

from module_workspace import create_workspace


def prepare(manifests, workspaces, go="go", offline=False, stage_names=None):
    manifests = Path(manifests).resolve()
    workspaces = Path(workspaces).resolve()
    if workspaces.is_relative_to(manifests):
        raise ValueError("workspaces must be outside the manifest inventory")
    if stage_names and any(Path(name).name != name for name in stage_names):
        raise ValueError("dependency stages must be direct children of the inventory")
    stages = ([manifests / name for name in stage_names] if stage_names else
              sorted(path for path in manifests.iterdir() if path.is_dir()))
    if not stages or any(not (stage / "go.mod").is_file() for stage in stages):
        raise ValueError("each dependency stage must include a root go.mod")
    for stage in stages:
        workspace = workspaces / stage.name / "go.work"
        create_workspace(stage, workspace, go)
        environment = {**os.environ, "GOWORK": str(workspace), "GOTOOLCHAIN": "local",
                       "GOMAXPROCS": "2", "GOFLAGS": "-p=2", "GOTELEMETRY": "off"}
        if offline:
            environment.update(GOPROXY="off", GOSUMDB="off")
        for arguments in (("list", "-m", "all"), ("mod", "download", "all")):
            command = [go, *arguments]
            print(f"dependency graph: stage={stage.name} offline={offline} command={command}", flush=True)
            subprocess.run(command, cwd=stage, env=environment, check=True)
    return len(stages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", type=Path)
    parser.add_argument("workspaces", type=Path)
    parser.add_argument("--go", default="go")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--stage", action="append")
    args = parser.parse_args()
    prepare(args.manifests, args.workspaces, args.go, args.offline, args.stage)
