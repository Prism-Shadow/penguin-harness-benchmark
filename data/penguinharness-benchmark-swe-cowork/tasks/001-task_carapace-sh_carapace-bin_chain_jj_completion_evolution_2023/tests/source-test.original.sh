#!/usr/bin/env bash
set -Eeuo pipefail

python3 /tests/grader.py \
  --repo /workspace \
  --tests-root /tests/native \
  --output /logs/verifier/ctrf.json \
  --reward /logs/verifier/reward.json

