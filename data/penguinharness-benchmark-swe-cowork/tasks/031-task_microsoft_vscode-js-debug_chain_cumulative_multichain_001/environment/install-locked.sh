#!/bin/sh
set -eu

error_log=$(mktemp)
trap 'rm -f "$error_log"' EXIT
attempt=1
while :; do
  if npm ci --no-audit --no-fund "$@" 2>"$error_log"; then
    cat "$error_log" >&2
    exit 0
  else
    status=$?
  fi
  cat "$error_log" >&2
  if [ "$attempt" -ge 3 ] || ! grep -Eq 'npm (ERR!|error) (code|errno) (FETCH_ERROR|EAI_AGAIN|ECONNRESET|ETIMEDOUT|ENETUNREACH|ECONNREFUSED|EHOSTUNREACH|EAI_FAIL)([[:space:]]|$)' "$error_log"; then
    exit "$status"
  fi
  printf 'Transient npm network failure; retrying locked install (%s/3)\n' "$((attempt + 1))" >&2
  sleep "$((attempt * 5))"
  attempt=$((attempt + 1))
done
