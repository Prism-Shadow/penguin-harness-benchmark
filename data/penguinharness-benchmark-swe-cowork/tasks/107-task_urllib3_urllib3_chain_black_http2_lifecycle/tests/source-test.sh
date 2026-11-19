#!/usr/bin/env bash
set -Eeuo pipefail
python3 "${SEGPIPE_TESTS_ROOT:-/tests}/grader.py"
