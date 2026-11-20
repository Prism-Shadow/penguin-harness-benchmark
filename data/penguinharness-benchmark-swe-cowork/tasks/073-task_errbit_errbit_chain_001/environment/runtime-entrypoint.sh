#!/bin/bash
set -euo pipefail
python3 /usr/local/lib/task-runtime-preflight.py --repo "${REPO_DIR:-/app/code}"
exec "$@"
