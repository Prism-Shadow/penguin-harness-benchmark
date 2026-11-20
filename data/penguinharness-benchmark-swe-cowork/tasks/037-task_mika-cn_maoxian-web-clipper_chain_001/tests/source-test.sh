#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export REPO_DIR="${REPO_DIR:-/workspace}"
TESTS_ROOT="${SEGPIPE_TESTS_ROOT:-/tests}"
exec python3 "$TESTS_ROOT/grader.py"
