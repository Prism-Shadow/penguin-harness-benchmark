#!/usr/bin/env bash
set -u
cd "${REPO_DIR:-/app/code}" || exit 2
git apply --binary --whitespace=nowarn /solution/solution.patch

