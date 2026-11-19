#!/bin/bash
set -Eeuo pipefail
cd /app/code
git apply --binary --whitespace=nowarn /solution/solution.patch
git apply --whitespace=nowarn /solution/contract-repair.patch
