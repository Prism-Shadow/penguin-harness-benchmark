#!/usr/bin/env bash
# Spend and clock guard of one GDPevo protocol replica. replica.sh starts it beside the steps;
# it can also run by hand against a replica's root and state dir:
#
#   tools/gdpevo/protocol/guard.sh --root <data root> --state-dir <dir> --limit-usd <n>
#       [--penguin "<command>"] [--interval 30] [--no-peak-guard]
#
# Every --interval seconds it adds the list cost of the trials under both GDPevo Benchmarks'
# .jobs/ in the root's default_project (tools/measure/spend.py: finished trials' cost_usd,
# in-flight ones' cost files), the cost of the root's host Sessions (`penguin cost --json`:
# the Project's whole usage table, which is the evaluator and optimizer Sessions and their
# subagents), and $0.25 for each trial still in its agent phase. When that exceeds
# --limit-usd, or a peak pricing window is less than 5 minutes away (tools/measure/peak.py;
# skipped with --no-peak-guard), it writes <state-dir>/ABORTED plus ABORTED_SPEND or
# ABORTED_PEAK, runs abort.sh on the root and exits. It also exits when <state-dir>/DONE
# exists or the driver (<state-dir>/replica.pid) is gone. The host reading is skipped while
# no server owns the root (and it names the server explicitly, so it never starts one).
# Log: <state-dir>/guard.log, one JSON line per reading.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
MEASURE="$(cd "$HERE/../../measure" && pwd)"
RESERVE_PER_TRIAL_USD=0.25
BENCHMARKS=(penguinharness-benchmark-gdpevo-train penguinharness-benchmark-gdpevo-test)

ROOT="" STATE_DIR="" LIMIT="" PENGUIN_CMD="penguin" INTERVAL=30 PEAK_GUARD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT=${2:?}; shift 2 ;;
    --state-dir) STATE_DIR=${2:?}; shift 2 ;;
    --limit-usd) LIMIT=${2:?}; shift 2 ;;
    --penguin) PENGUIN_CMD=${2:?}; shift 2 ;;
    --interval) INTERVAL=${2:?}; shift 2 ;;
    --no-peak-guard) PEAK_GUARD=0; shift ;;
    -h|--help) usage ;;
    *) echo "unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$ROOT" ] && [ -n "$STATE_DIR" ] && [ -n "$LIMIT" ] || usage
read -ra PENGUIN <<< "$PENGUIN_CMD"
mkdir -p "$STATE_DIR"
LOG="$STATE_DIR/guard.log"
log() { echo "$(date -Is) $*" >> "$LOG"; }

driver_running() {
  local pid
  pid=$(cat "$STATE_DIR/replica.pid" 2>/dev/null || true)
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

server_port() {
  PENGUIN_HOME="$ROOT" "${PENGUIN[@]}" server status --root "$ROOT" 2>/dev/null | python3 -c '
import json, sys
status = json.load(sys.stdin)
print(status["port"] if status.get("running") and status.get("port") else "")' 2>/dev/null || true
}

# Trial spend of both Benchmarks as one JSON object (spend.py's fields, summed).
trial_spend() {
  local bench jobs readings=()
  for bench in "${BENCHMARKS[@]}"; do
    jobs="$ROOT/default_project/benchmarks/$bench/.jobs"
    [ -d "$jobs" ] || continue
    readings+=("$(python3 "$MEASURE/spend.py" "$jobs" '*')")
  done
  python3 -c '
import json, sys
total = {"cost_usd": 0.0, "finished": 0, "errors": 0, "verifying": 0, "in_agent_phase": 0, "cost_from_logs": 0}
for text in sys.argv[1:]:
    for key, value in json.loads(text).items():
        total[key] = total.get(key, 0) + value
total["cost_usd"] = round(total["cost_usd"], 4)
print(json.dumps(total))' "${readings[@]}"
}

# Host spend: {"cost_usd": <total or 0>, "uncosted": <bool>, "requests": n}; {} when no server runs.
host_spend() {
  local port
  port=$(server_port)
  [ -n "$port" ] || { echo '{}'; return; }
  # Named explicitly so that this call can never start a server; on localhost, the app host
  # the API token is accepted on (a 127.0.0.1 URL answers 401).
  PENGUIN_HOME="$ROOT" "${PENGUIN[@]}" cost --json --project-id default_project --server "http://localhost:$port" 2>/dev/null | python3 -c '
import json, sys
total = json.load(sys.stdin)["summary"]["total"]
print(json.dumps({"cost_usd": round(total.get("cost") or 0.0, 4), "uncosted": bool(total.get("hasUncosted")),
                  "requests": total.get("requests", 0)}))' 2>/dev/null || echo '{}'
}

peak_soon() { # 0: a peak window is less than 5 minutes away (or peak.py failed: pausing is the safe side)
  local out rc=0
  out=$(python3 "$MEASURE/peak.py" --within 5m 2>&1) || rc=$?
  case $rc in
    0) log "$out"; return 0 ;;
    1) return 1 ;;
    *) log "peak.py failed ($rc): $out"; return 0 ;;
  esac
}

if [ "$PEAK_GUARD" = 1 ]; then
  rc=0
  python3 "$MEASURE/peak.py" --within 5m > /dev/null || rc=$?
  [ "$rc" -le 1 ] || { echo "peak.py does not run (exit $rc); fix it or pass --no-peak-guard" >&2; exit 2; }
fi

LAST_HOST='{}'
log "start: limit $LIMIT USD, reserve $RESERVE_PER_TRIAL_USD USD per trial in its agent phase, root $ROOT"
while true; do
  trials=$(trial_spend) || trials='{"cost_usd": 0, "in_agent_phase": 0}'
  host=$(host_spend)
  if [ "$host" != '{}' ]; then LAST_HOST=$host; fi
  reading=$(python3 -c '
import json, sys
trials, host, limit, reserve = json.loads(sys.argv[1]), json.loads(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
total = trials.get("cost_usd", 0) + host.get("cost_usd", 0) + reserve * trials.get("in_agent_phase", 0)
print(json.dumps({"total_usd": round(total, 4), "trials": trials, "host": host, "over": total > limit}))' \
    "$trials" "$LAST_HOST" "$LIMIT" "$RESERVE_PER_TRIAL_USD") || reading='{"over": false}'
  log "$reading"
  over=0
  case "$reading" in *'"over": true'*) over=1 ;; esac
  peak=0
  if [ "$PEAK_GUARD" = 1 ] && peak_soon; then peak=1; fi
  if [ "$over" = 1 ] || [ "$peak" = 1 ]; then
    touch "$STATE_DIR/ABORTED"
    [ "$over" = 1 ] && touch "$STATE_DIR/ABORTED_SPEND"
    [ "$peak" = 1 ] && touch "$STATE_DIR/ABORTED_PEAK"
    log "ABORTING (spend over the limit: $over, peak window: $peak)"
    "$HERE/abort.sh" --root "$ROOT" --penguin "$PENGUIN_CMD" >> "$LOG" 2>&1 || log "abort.sh failed"
    exit 0
  fi
  if [ -f "$STATE_DIR/DONE" ]; then log "driver done"; exit 0; fi
  if ! driver_running; then log "driver not running"; exit 0; fi
  sleep "$INTERVAL"
done
