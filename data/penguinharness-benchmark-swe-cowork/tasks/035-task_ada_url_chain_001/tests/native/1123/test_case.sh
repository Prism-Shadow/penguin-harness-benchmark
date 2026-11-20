#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$TASK_ROOT/environment/run_probe.py" --case simple_absolute --node 1123
