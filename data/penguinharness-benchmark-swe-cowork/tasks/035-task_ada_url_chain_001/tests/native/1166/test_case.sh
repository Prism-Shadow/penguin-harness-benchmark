#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$TASK_ROOT/environment/run_probe.py" --case protocol_port_zero --node 1166
