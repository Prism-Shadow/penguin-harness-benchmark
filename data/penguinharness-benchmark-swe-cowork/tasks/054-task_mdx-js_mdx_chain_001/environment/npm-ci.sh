#!/bin/sh
set -eu

export npm_config_jobs=2 MAKEFLAGS=-j2 UV_THREADPOOL_SIZE=2
log_file=$(mktemp "${TMPDIR:-/tmp}/mdx-npm-ci.XXXXXX")
trap 'rm -f "$log_file"' EXIT
attempt=1
while :; do
  printf 'Frozen npm ci attempt %s/3\n' "$attempt"
  if npm ci --include=dev --include=optional --foreground-scripts \
    --no-audit --no-fund --prefer-offline \
    --maxsockets=2 --fetch-retries=2 --fetch-timeout=300000 \
    --fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=60000 \
    --loglevel=http >"$log_file" 2>&1; then
    cat "$log_file"
    exit 0
  else
    status=$?
  fi
  cat "$log_file" >&2
  failure_code=$(sed -nE 's/^npm (error|ERR!) code ([^[:space:]]+)[[:space:]]*$/\2/p' "$log_file")
  retry=false
  case "$failure_code" in
    ETIMEDOUT|ECONNRESET|EAI_AGAIN|ENETUNREACH|EHOSTUNREACH|ECONNREFUSED|E502|E503|E504) retry=true ;;
  esac
  if [ "$attempt" -ge 3 ] || [ "$retry" != true ]; then
    printf 'Frozen npm ci failed (exit %s); dependency preflight must not run.\n' "$status" >&2
    exit "$status"
  fi
  printf 'Transient registry failure; retrying the same lockfile with retained npm cache.\n' >&2
  sleep "$((attempt * 10))"
  attempt=$((attempt + 1))
done
