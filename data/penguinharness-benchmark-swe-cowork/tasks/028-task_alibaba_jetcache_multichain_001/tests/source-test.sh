#!/usr/bin/env bash
set -Eeuo pipefail
tests="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$tests/run_suite.py"
