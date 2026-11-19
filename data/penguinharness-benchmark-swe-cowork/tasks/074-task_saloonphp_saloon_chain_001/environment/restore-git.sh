#!/bin/bash
set -euo pipefail
cd /app/code
rm -rf .git
git init -q
git config user.name 'Saloon Benchmark'
git config user.email benchmark@example.invalid
git add -A
GIT_AUTHOR_DATE=2026-09-20T00:00:00Z GIT_COMMITTER_DATE=2026-09-20T00:00:00Z git commit -qm 'Frozen Saloon source baseline'
git rev-parse HEAD
test "$(git rev-parse HEAD)" = "$(cat /opt/saloon-baseline.sha)"
git config --system --add safe.directory /app/code
chmod -R a+rwX .git
