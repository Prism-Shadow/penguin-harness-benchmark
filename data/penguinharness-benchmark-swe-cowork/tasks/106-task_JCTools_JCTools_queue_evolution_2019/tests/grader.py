#!/usr/bin/env python3
"""The shell verifier writes the canonical reward object for Pier."""
from pathlib import Path
import json

path = Path("/logs/verifier/reward.json")
if not path.is_file():
    raise SystemExit("missing verifier reward")
value = json.loads(path.read_text())
if not isinstance(value, dict) or "reward" not in value:
    raise SystemExit("invalid verifier reward")
print(json.dumps(value, sort_keys=True))
