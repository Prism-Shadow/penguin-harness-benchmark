#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="${REPO_DIR:-/workspace}"
git -C "$REPOSITORY" apply --binary --whitespace=nowarn /solution/solution.patch

