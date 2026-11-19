#!/bin/bash
set -euo pipefail
exec python3 /tests/test_outputs.py "$@"
