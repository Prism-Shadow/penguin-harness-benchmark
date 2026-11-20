#!/usr/bin/env bash
set -Eeuo pipefail
cd /app/code
git apply --binary /solution/solution.patch
/opt/task-runtime/bin/python3 setup.py build_ext --inplace -j 2
