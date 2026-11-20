#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$TASK_ROOT/environment/run_probe.py" --case idna_ascii --node 1065
