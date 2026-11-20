#!/usr/bin/env bash
set -euo pipefail
cd /workspace
git apply --binary --whitespace=nowarn /solution/solution.patch
