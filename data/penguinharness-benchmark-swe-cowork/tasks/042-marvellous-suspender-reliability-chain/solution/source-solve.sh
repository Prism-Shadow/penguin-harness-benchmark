#!/usr/bin/env bash
set -euo pipefail
repo="${REPO_DIR_OVERRIDE:-${REPO_DIR:-/app/code}}"
cd "$repo"
git apply --binary --whitespace=nowarn /solution/solution.patch
