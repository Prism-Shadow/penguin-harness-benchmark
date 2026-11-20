#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
python3 /tests/run_contract_tests.py
python3 /tests/grader.py
exit 0

