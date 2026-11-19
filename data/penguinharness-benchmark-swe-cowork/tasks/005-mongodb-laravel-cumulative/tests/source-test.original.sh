#!/bin/bash
set -euo pipefail
export REPO_DIR="${REPO_DIR:-/workspace}"
export SEGPIPE_TESTS_ROOT="${SEGPIPE_TESTS_ROOT:-/tests}"
python3 /tests/grader.py
