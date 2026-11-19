#!/usr/bin/env bash
set -euo pipefail
export REPO_DIR="${REPO_DIR:-/app/code}"
exec /usr/local/bin/python /tests/grader.py

