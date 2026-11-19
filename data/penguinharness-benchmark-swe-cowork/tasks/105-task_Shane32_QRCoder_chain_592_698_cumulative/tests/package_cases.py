#!/usr/bin/env python3
"""Repack only the editable behavior source; retain all frozen node metadata."""
import argparse
import base64
import gzip
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    packed = root / "pr_commands.json.gz.b64"
    payload = json.loads(gzip.decompress(base64.b64decode(packed.read_bytes())))
    source = (root / "behavior_cases.cs").read_text()
    if args.check:
        if payload["behavior_cases_cs"] != source:
            raise SystemExit("behavior source differs from packed dispatcher input")
        print("behavior source and packed dispatcher input agree")
        return
    payload["behavior_cases_cs"] = source
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    packed.write_bytes(base64.b64encode(gzip.compress(raw, mtime=0)) + b"\n")


if __name__ == "__main__":
    main()
