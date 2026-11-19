#!/bin/bash
set -euo pipefail
repo="${REPO_DIR_OVERRIDE:-${REPO_DIR:-/app/code}}"
git -c safe.directory="$repo" -C "$repo" apply --binary --whitespace=nowarn /solution/solution.patch

