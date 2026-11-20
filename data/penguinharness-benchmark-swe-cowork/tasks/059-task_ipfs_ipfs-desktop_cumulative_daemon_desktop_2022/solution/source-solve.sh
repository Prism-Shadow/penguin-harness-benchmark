#!/usr/bin/env bash
set -Eeuo pipefail
git -C /app/code apply --binary --whitespace=nowarn /solution/solution.patch
