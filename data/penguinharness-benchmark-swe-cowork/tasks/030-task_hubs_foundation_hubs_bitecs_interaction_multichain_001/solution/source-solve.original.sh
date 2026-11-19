#!/usr/bin/env bash
set -Eeuo pipefail
git -C /app apply --binary --whitespace=nowarn /solution/solution.patch
