#!/usr/bin/env bash
set -Eeuo pipefail
git -c safe.directory=/app -C /app apply --binary --whitespace=nowarn /solution/solution.patch
