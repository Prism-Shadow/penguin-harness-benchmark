#!/usr/bin/env bash
set -Eeuo pipefail
unset NODE_PATH NODE_OPTIONS
mkdir -p /logs/verifier
set +e
bash /tests/prepare-dependencies.sh > /logs/verifier/dependency-setup.log 2>&1
export DEPENDENCY_SETUP_EXIT_CODE=$?
set -e
python3 /tests/grader.py
