#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_DIR:-/app/code}"
git apply --check --binary /solution/solution.patch
git apply --binary --whitespace=nowarn /solution/solution.patch
