#!/usr/bin/env bash
set -euo pipefail
node /opt/task-runtime/check-runtime.cjs "${REPO_DIR:-$PWD}"
exec "$@"
