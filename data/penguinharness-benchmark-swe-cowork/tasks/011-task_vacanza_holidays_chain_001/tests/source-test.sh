#!/bin/bash
set -euo pipefail
export REPO_DIR_OVERRIDE="${REPO_DIR_OVERRIDE:-/app/code}"
exec python3 /tests/grader.py
