#!/usr/bin/env python3
import json
from pathlib import Path

reward = json.loads(Path("/logs/verifier/reward.json").read_text())
print(json.dumps(reward, sort_keys=True))
