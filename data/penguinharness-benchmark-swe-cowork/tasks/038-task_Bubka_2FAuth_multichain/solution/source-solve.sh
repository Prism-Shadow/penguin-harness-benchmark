#!/bin/sh
set -eu
cd /app/code
git apply --check --binary /solution/solution.patch
git apply --binary --whitespace=nowarn /solution/solution.patch
