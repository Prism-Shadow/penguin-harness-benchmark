#!/usr/bin/env bash
set -euo pipefail
repo_dir="${REPO_DIR:-/app/code}"
patch_path="$(cd "$(dirname "$0")" && pwd)/solution.patch"
git -C "$repo_dir" apply --binary --whitespace=nowarn "$patch_path"
