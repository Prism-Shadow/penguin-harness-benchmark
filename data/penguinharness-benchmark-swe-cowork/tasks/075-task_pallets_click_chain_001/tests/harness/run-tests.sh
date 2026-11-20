#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${1:-}" = --all ]; then shift; fi
exec python3 -B "$ROOT/run_contracts.py" "$@"
