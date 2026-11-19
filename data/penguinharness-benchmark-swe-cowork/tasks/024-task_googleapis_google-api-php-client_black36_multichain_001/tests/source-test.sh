#!/usr/bin/env bash
set -eu
tests_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$tests_root/run_contracts.py" "$@"
