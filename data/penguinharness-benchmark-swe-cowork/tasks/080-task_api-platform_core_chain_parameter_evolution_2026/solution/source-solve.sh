#!/bin/sh
set -eu
cd /app/code
git apply --binary --whitespace=nowarn /solution/solution.patch
