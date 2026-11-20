#!/usr/bin/env bash
set -euo pipefail
git -C /app/code apply --binary --whitespace=nowarn /solution/solution.patch
