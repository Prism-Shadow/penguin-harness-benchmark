#!/usr/bin/env bash
set -Eeuo pipefail

repo=${REPO_DIR_OVERRIDE:-${REPO_DIR:-/workspace}}
git -c safe.directory="$repo" -C "$repo" apply --binary --whitespace=nowarn /solution/solution.patch
