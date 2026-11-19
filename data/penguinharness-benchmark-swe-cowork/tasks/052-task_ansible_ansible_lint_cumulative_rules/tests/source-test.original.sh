#!/bin/bash
set -euo pipefail
export REPO_DIR="${REPO_DIR:-/workspace}"
export REPO_DIR_OVERRIDE="${REPO_DIR_OVERRIDE:-$REPO_DIR}"
exec python3 /tests/grader.py

