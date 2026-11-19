import argparse
import json
import sys
import sysconfig
import tomllib
from pathlib import Path


def register(repository):
    project = tomllib.loads((repository / "pyproject.toml").read_text())["project"]
    site = Path(sysconfig.get_path("purelib"))
    metadata = site / "black-25.9.0+task.dist-info"
    metadata.mkdir(exist_ok=True)
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: black\nVersion: 25.9.0+task\n"
        + "".join(f"Requires-Dist: {requirement}\n" for requirement in project["dependencies"]))
    groups = {"console_scripts": project["scripts"], **project["entry-points"]}
    (metadata / "entry_points.txt").write_text("\n".join(
        f"[{group}]\n" + "\n".join(f"{name} = {entry}" for name, entry in entries.items())
        for group, entries in groups.items()) + "\n")
    (metadata / "direct_url.json").write_text(json.dumps({
        "url": repository.as_uri(), "dir_info": {"editable": True}}))
    (site / "black-task-source.pth").write_text(str(repository / "src") + "\n")
    for name, entry in project["scripts"].items():
        module, function = entry.split(" [")[0].split(":")
        script = Path(sysconfig.get_path("scripts")) / name
        script.write_text(f"#!{sys.executable}\nfrom {module} import {function}\n{function}()\n")
        script.chmod(0o755)
    print(f"Registered only source paths and declared entry points: {repository}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    register(parser.parse_args().repository.resolve())
