#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_DIR:-/workspace}"
git apply --binary --whitespace=nowarn /solution/solution.patch
