#!/bin/bash
set -euo pipefail
repo="${REPO_DIR:-/app/code}"
git -c safe.directory="$repo" -C "$repo" apply --binary --whitespace=nowarn /solution/solution.patch
