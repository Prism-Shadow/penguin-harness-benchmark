#!/bin/bash
set -u

python3 "${TESTS_ROOT:-/tests}/run_native.py"
status=$?

exit "$status"
