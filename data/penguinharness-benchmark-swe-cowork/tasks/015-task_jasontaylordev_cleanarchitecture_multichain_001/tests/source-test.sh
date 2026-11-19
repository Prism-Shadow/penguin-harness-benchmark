#!/usr/bin/env bash
set -Eeuo pipefail
python3 /tests/stage_runtime.py
rm -rf /tmp/segpipe-probe-cache
exec bash /tests/source-test.original.sh
