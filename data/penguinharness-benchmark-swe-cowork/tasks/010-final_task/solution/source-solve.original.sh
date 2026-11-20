#!/usr/bin/env bash
set -euo pipefail

git -C /workspace apply --binary --whitespace=nowarn /solution/solution.patch

