#!/usr/bin/env bash
set -euo pipefail
git config --global --add safe.directory /app/code
git -C /app/code apply --binary --whitespace=nowarn /solution/solution.patch

