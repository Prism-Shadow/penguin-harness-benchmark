#!/usr/bin/env bash
set -Eeuo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export JETCACHE_TASK_ROOT="$TASK_ROOT"
exec bash "$TASK_ROOT/native-task/environment/run_behavior.sh" 989
