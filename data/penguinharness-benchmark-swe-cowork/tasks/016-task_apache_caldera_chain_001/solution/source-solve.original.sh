#!/bin/bash
set -euo pipefail
cd /app
git apply --binary --whitespace=nowarn /solution/solution.patch
