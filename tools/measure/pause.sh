#!/usr/bin/env bash
# Pauses a measurement: stops its `harbor run` processes, then, for every trial still in
# flight, reads the spend its in-container PenguinHarness server has recorded and removes
# the trial's containers.
#
#   tools/measure/pause.sh --jobs-dir <dir> --job-glob <glob> [--job-glob <glob>]...
#
# A job matches when its name (harbor run --job-name) matches one of the shell globs, for
# example "*-attempt-2*". Stopping Harbor alone would leave the trial containers, and the
# agents in them, running. The cost a removed trial had incurred is not in any result.json,
# so each one is printed (USD at list price, or "unknown"): add it to the ledger by hand.
# Only processes of the current user are signalled. guard.sh calls this; it can also be
# run by hand.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" >&2; exit 2; }

# Where the adapter installs PenguinHarness inside a task container (agents/penguin_agent/agent.py PREFIX).
PREFIX=/opt/penguin-bench

JOBS_DIR=""
GLOBS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --jobs-dir) JOBS_DIR=${2:?}; shift 2 ;;
    --job-glob) GLOBS+=("${2:?}"); shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$JOBS_DIR" ] && [ "${#GLOBS[@]}" -gt 0 ] || usage

matches() { # <job name>: 0 when it matches one of the globs
  local pattern
  for pattern in "${GLOBS[@]}"; do
    # shellcheck disable=SC2053  # the glob is meant to match
    [[ $1 == $pattern ]] && return 0
  done
  return 1
}

stamp() { date -Is; }

stopped=0
while read -r pid args; do
  [ -n "$pid" ] || continue
  name=$(sed -n 's/.*--job-name[ =]\([^ ]*\).*/\1/p' <<< "$args")
  if [ -n "$name" ] && matches "$name"; then
    kill -TERM "$pid" 2>/dev/null && stopped=$((stopped + 1))
  fi
done < <(pgrep -u "$(id -u)" -af 'harbor run' || true)
echo "$(stamp) sent SIGTERM to $stopped harbor process(es)"
[ "$stopped" = 0 ] || sleep 10

shopt -s nullglob
for job in "$JOBS_DIR"/*/; do
  job=${job%/}
  matches "$(basename "$job")" || continue
  for trial in "$job"/*__*; do
    [ -d "$trial" ] && [ ! -f "$trial/result.json" ] || continue
    # Harbor names a trial's Compose projects after the lower-cased trial directory name.
    prefix=$(basename "$trial" | tr '[:upper:]' '[:lower:]')
    for container in $(docker ps --format '{{.Names}}' | awk -v p="${prefix}__" 'index($0, p) == 1' || true); do
      cost=$(timeout 30 docker exec -u 0 -e PENGUIN_HOME="$PREFIX/home" -w "$PREFIX" "$container" \
        "$PREFIX/bin/penguin" cost --by session --days 7 --json 2>/dev/null | python3 -c '
import json, sys
try:
    groups = json.loads(sys.stdin.read()).get("groups") or []
    print(round(sum(g.get("cost") or 0 for g in groups), 5))
except Exception:
    print("unknown")' 2>/dev/null || true)
      [ -n "$cost" ] || cost=unknown
      docker rm -f "$container" > /dev/null 2>&1 || true
      echo "$(stamp) removed $container (trial $(basename "$trial")), unrecorded cost $cost"
    done
  done
done
