"""Keep the public release-input artifact in sync with the offline image lock."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    artifact_path = root / "environment/workplace-service/original/authoring/corpus/artifacts.json"
    artifacts = json.loads(artifact_path.read_text())
    lock = (root / "environment/offline-inputs/image-lock.json").read_text()
    matches = [artifact for artifact in artifacts["artifacts"] if artifact["id"] == "r29-image-lock-v1"]
    if len(matches) != 1:
        raise SystemExit("public release-input artifact must have exactly one entry")
    if matches[0]["body"] != lock:
        if args.check:
            raise SystemExit("stale public release-input artifact")
        matches[0]["body"] = lock
        artifact_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n")
    print("Public release-input artifact matches the offline image lock")


if __name__ == "__main__":
    main()
