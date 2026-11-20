#!/usr/bin/env python3
import json
from pathlib import Path
print(json.dumps(json.loads(Path("/logs/verifier/reward.json").read_text())))
