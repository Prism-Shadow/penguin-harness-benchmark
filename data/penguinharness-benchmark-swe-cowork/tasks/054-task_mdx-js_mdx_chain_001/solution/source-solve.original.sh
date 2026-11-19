#!/bin/bash
set -Eeuo pipefail

repo_dir="${REPO_DIR:-/workspace}"
patch_file="${GOLD_PATCH:-/solution/solution.patch}"

git -C "$repo_dir" apply --binary --whitespace=nowarn "$patch_file"
