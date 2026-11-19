import argparse
import json
import os
from pathlib import Path
import subprocess


PACKAGES = {
    "typescript": "5.9.3",
    "jest": "29.7.0",
    "jest-environment-jsdom": "29.7.0",
    "jest-sonar": "0.2.16",
    "@swc/core": "1.11.24",
    "@swc/jest": "0.2.39",
    "@testing-library/jest-dom": "6.6.3",
    "@types/jest": "29.5.14",
    "@types/node": "22.15.3",
    "@types/react": "19.2.2",
    "@types/react-dom": "19.2.2",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = Path(__file__).resolve().parents[1] / "environment"
    manifest = json.loads((environment / "package.json").read_text())
    manifest["dependencies"].update(PACKAGES)
    (output / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "package-lock.json").write_bytes((environment / "package-lock.json").read_bytes())
    env = {**os.environ, "GOMAXPROCS": "2", "UV_THREADPOOL_SIZE": "2", "npm_config_jobs": "2"}
    command = ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund",
               "--cache", str(args.cache.resolve() if args.cache else output / "cache"), "--maxsockets=2", "--fetch-retries=0", "--fetch-timeout=20000"]
    if args.offline:
        command.append("--offline")
    subprocess.run(command, cwd=output, env=env, check=True)
    lock = json.loads((output / "package-lock.json").read_text())
    assert lock["packages"][""]["dependencies"] == manifest["dependencies"]
    for name, version in PACKAGES.items():
        assert lock["packages"]["node_modules/" + name]["version"] == version
    for name, entry in lock["packages"].items():
        if not name:
            continue
        assert entry.get("resolved", "").startswith("https://registry.npmjs.org/"), name
        assert entry.get("integrity", "").startswith("sha512-"), name
        assert not any(marker in name for marker in ("@ledgerhq/", "@features/", "@domain/", "@devtools/")), name
    print("Prepared complete registry-resolved lock; review it, npm ci in isolation, and run retained package commands before promotion. No active candidate file was changed.")


if __name__ == "__main__":
    main()
