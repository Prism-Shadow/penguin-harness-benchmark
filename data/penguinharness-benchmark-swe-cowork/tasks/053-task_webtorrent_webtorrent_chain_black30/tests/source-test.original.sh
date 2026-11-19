#!/usr/bin/env bash
set -u
mkdir -p /logs/verifier
export REPO_DIR="${REPO_DIR:-/app/code}"
export SEGPIPE_TESTS_ROOT="${SEGPIPE_TESTS_ROOT:-/tests}"
python3 /tests/grade_runner.py

