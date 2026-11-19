#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
export REPO_DIR="${REPO_DIR:-/workspace}"
python3 /tests/grader.py

