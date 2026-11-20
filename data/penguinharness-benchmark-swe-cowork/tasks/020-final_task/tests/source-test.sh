#!/usr/bin/env bash
set -euo pipefail
"${TASK_PYTHON:-/opt/task-python/bin/python}" /tests/grader.py
