#!/usr/bin/env bash
set -Eeuo pipefail
cd "${REPO_DIR:-/app/code}"
export npm_config_jobs=2 MAKEFLAGS=-j2
timeout 600s /usr/local/bin/offline-npm ci --offline --no-audit --no-fund
