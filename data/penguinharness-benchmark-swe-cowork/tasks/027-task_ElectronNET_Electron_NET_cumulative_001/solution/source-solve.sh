#!/usr/bin/env bash
set -Eeuo pipefail
export REPO_DIR_OVERRIDE="${REPO_DIR_OVERRIDE:-/app/code}"
export GOLD_PATCHES_DIR=/solution/gold_patches
exec bash /solution/source-solution.sh
