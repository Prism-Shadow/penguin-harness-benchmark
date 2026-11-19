#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace
git apply --binary --whitespace=nowarn /solution/solution.patch
