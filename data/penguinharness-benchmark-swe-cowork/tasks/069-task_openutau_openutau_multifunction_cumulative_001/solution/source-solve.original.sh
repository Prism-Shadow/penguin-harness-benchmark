#!/bin/bash
set -euo pipefail
git -c safe.directory=/workspace -C /workspace apply --binary --whitespace=nowarn /solution/solution.patch
