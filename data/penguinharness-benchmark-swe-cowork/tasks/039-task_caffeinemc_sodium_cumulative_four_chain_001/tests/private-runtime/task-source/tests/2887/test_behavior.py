#!/usr/bin/env python3
"""Node-specific executable behavior check for scheduled PR 2887."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[2]
runner = TASK_ROOT / "environment" / "behavior_runner.py"
environment = os.environ.copy()
environment.setdefault("SEGPIPE_TASK_ROOT", str(TASK_ROOT))
environment.setdefault("REPO_DIR", str(TASK_ROOT / "base"))
environment.setdefault("REPO_DIR_OVERRIDE", environment["REPO_DIR"])
raise SystemExit(subprocess.call([sys.executable, str(runner), "--pr", "2887"], env=environment))
