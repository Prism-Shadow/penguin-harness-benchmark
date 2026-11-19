#!/usr/bin/env bash
set -Eeuo pipefail

git -C /workspace apply --binary --whitespace=nowarn /solution/solution.patch

