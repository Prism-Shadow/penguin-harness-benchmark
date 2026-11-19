#!/usr/bin/env bash
set -Eeuo pipefail
cd /app
git apply --binary --whitespace=nowarn /solution/solution.patch
