#!/usr/bin/env bash
set -Eeuo pipefail
cd /app/code
git apply --binary --whitespace=nowarn /solution/solution.patch
git apply --binary --whitespace=nowarn /solution/repair.patch
