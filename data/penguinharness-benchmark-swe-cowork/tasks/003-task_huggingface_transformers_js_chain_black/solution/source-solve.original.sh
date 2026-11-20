#!/usr/bin/env bash
set -euo pipefail
git config --global --add safe.directory /workspace
git -C /workspace apply --binary --whitespace=nowarn /solution/solution.patch
