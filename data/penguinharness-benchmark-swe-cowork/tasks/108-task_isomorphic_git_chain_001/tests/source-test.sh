#!/bin/bash
set -euo pipefail
export REPO_DIR_OVERRIDE="${REPO_DIR_OVERRIDE:-${REPO_DIR:-/workspace}}"
exec /usr/bin/python3 /tests/test_outputs.py
