#!/usr/bin/env bash
set -Eeuo pipefail
git -C "${REPO_DIR_OVERRIDE:-${REPO_DIR:-/app/code}}" apply --binary --whitespace=nowarn "${SOLUTION_DIR:-/solution}/solution.patch"
