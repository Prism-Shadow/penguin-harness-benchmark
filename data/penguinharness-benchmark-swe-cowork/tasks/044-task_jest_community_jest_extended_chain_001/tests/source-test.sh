#!/usr/bin/env bash
set -Eeuo pipefail
rm -f /logs/verifier/reward.json /logs/verifier/ctrf.json
python3 /tests/grader.py
test -s /logs/verifier/reward.json
test -s /logs/verifier/ctrf.json

