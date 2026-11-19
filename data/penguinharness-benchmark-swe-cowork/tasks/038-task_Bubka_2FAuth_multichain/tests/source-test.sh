#!/bin/sh
set -eu
TESTS_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export REPO_DIR="${REPO_DIR:-/app/code}"
exec python3 "$TESTS_ROOT/grader.py"
