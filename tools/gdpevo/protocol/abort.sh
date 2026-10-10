#!/usr/bin/env bash
# Aborts one GDPevo protocol replica: stops the server that owns its data root (which ends
# the evaluator and optimizer Sessions), sends SIGTERM to this user's `harbor run` processes
# that write under the root's Benchmarks, then removes the containers of the trials still in
# flight, reading each one's unrecorded spend first, as tools/measure/pause.sh does. Only
# processes of the current user are signalled, and only containers named after this root's
# trial directories are removed; other replicas and other jobs on the machine are untouched.
# guard.sh calls this; it can also run by hand.
#
#   tools/gdpevo/protocol/abort.sh --root <data root> [--penguin "<command>"]
set -uo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" >&2; exit 2; }

# Where the adapter installs PenguinHarness inside a task container (agents/penguin_agent/agent.py PREFIX).
PREFIX=/opt/penguin-bench
BENCHMARKS=(penguinharness-benchmark-gdpevo-train penguinharness-benchmark-gdpevo-test)

ROOT="" PENGUIN_CMD="penguin"
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT=${2:?}; shift 2 ;;
    --penguin) PENGUIN_CMD=${2:?}; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$ROOT" ] || usage
read -ra PENGUIN <<< "$PENGUIN_CMD"
stamp() { date -Is; }

echo "$(stamp) stopping the server on $ROOT: $(PENGUIN_HOME="$ROOT" "${PENGUIN[@]}" server stop --root "$ROOT" 2>&1)"

stopped=0
while read -r pid args; do
  [ -n "$pid" ] || continue
  case "$args" in
    *"$ROOT/"*) kill -TERM "$pid" 2>/dev/null && stopped=$((stopped + 1)) ;;
  esac
done < <(pgrep -u "$(id -u)" -af 'harbor run' || true)
echo "$(stamp) sent SIGTERM to $stopped harbor process(es) of this root"
[ "$stopped" = 0 ] || sleep 10

shopt -s nullglob
for bench in "${BENCHMARKS[@]}"; do
  for trial in "$ROOT/default_project/benchmarks/$bench/.jobs"/*/*__*; do
    [ -d "$trial" ] && [ ! -f "$trial/result.json" ] || continue
    # Harbor names a trial's Compose project after the lower-cased trial directory name.
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
