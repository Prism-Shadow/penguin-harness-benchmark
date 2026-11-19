#!/usr/bin/env bash
set -Eeuo pipefail

patch_path="${GOLD_PATCH_PATH:-/solution/solution.patch}"
repo="${REPO_DIR:-/workspace}"
git -C "$repo" apply --binary --whitespace=nowarn "$patch_path"

