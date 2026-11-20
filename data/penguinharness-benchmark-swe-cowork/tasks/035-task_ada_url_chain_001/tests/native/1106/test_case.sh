#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$TASK_ROOT/environment/run_probe.py" --case can_parse_agreement --node 1106
