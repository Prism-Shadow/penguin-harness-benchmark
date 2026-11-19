#!/usr/bin/env bash
set -euo pipefail
cd /workspace
patch --batch --forward -p1 < /solution/solution.patch

