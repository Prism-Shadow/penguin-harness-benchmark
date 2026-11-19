#!/usr/bin/env bash
set -euo pipefail
repo=/app/code
patch=/solution/solution.patch
git -C "$repo" apply --binary --whitespace=nowarn "$patch"

