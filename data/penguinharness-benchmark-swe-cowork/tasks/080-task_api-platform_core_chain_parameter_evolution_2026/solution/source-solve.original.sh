#!/bin/sh
set -eu
cd /workspace
git apply --binary --whitespace=nowarn /solution/solution.patch
