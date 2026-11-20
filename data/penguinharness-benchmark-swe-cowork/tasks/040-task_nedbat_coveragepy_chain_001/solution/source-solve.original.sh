#!/usr/bin/env bash
set -Eeuo pipefail
git -C /workspace apply --binary /solution/solution.patch
python3 setup.py build_ext --inplace
