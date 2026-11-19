#!/usr/bin/env bash
set -euo pipefail
cd /app/code
git apply --binary --whitespace=nowarn /solution/solution.patch
