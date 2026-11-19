#!/usr/bin/env bash
set -euo pipefail
repo="${REPO_DIR_OVERRIDE:-${REPO_DIR:-/workspace}}"
git -C "$repo" apply --binary --whitespace=nowarn /solution/solution.patch
