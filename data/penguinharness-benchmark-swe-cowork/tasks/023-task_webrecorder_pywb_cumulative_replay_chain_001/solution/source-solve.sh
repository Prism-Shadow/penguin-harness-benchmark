#!/usr/bin/env bash
set -euo pipefail
cd /app/code
git apply --check --binary /solution/solution.patch
git apply --binary /solution/solution.patch
