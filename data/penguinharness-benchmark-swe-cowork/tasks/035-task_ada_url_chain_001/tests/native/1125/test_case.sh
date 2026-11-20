#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$TASK_ROOT/environment/run_probe.py" --case malformed_utf8 --node 1125
