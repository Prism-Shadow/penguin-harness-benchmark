#!/bin/bash
set -euo pipefail
repo=${REPO_DIR_OVERRIDE:-${REPO_DIR:-/workspace}}
git -C "$repo" apply --binary --whitespace=nowarn "$(dirname "$0")/solution.patch"
