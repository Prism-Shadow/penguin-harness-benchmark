#!/usr/bin/env bash
set -uo pipefail
exec python3 "$(dirname "$0")/run_probes.py"
