#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_DIR:-/app/code}"
git apply --whitespace=nowarn /solution/solution.patch
