#!/usr/bin/env bash
set -euo pipefail
git -C /workspace apply --binary /solution/solution.patch
