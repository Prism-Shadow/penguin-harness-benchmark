#!/bin/bash
set -euo pipefail
git -c safe.directory=/app/code -C /app/code apply --binary --whitespace=nowarn /solution/solution.patch
