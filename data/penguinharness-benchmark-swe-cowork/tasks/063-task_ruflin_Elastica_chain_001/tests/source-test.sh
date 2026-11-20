#!/usr/bin/env bash
set -euo pipefail

export REPO_DIR="${REPO_DIR:-/workspace}"
export REPO_DIR_OVERRIDE="$REPO_DIR"
python3 /tests/grader.py
