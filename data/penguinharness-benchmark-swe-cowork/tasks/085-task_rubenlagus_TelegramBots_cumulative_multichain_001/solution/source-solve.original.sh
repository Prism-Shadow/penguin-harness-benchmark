#!/usr/bin/env bash
set -euo pipefail
repo=/workspace
patch=/solution/solution.patch
git -C "$repo" apply --binary --whitespace=nowarn "$patch"

