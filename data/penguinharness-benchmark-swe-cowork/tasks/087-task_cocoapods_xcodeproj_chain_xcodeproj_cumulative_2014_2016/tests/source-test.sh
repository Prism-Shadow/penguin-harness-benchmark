#!/usr/bin/env bash
set -euo pipefail
export REPO_DIR="${REPO_DIR_OVERRIDE:-${REPO_DIR:-/workspace}}"
exec python3 /tests/grader.py
