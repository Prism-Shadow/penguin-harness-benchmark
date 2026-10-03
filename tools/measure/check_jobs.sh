#!/usr/bin/env bash
# Checks the job directories of a measurement before anything from them is published, and
# prints counts only:
#   1. how many files contain the configured key (read from --key-file, never printed), and
#      how many contain anything shaped like a DeepSeek key;
#   2. with a pilot.json or another `tools/summarize.py` records file, how each priced trial
#      was priced: its cost over the catalog peak price of its tokens (0.5000 = off-peak,
#      1.0000 = peak), and which trials have an incomplete cost.
#
#   tools/measure/check_jobs.sh --jobs-dir <dir> --key-file <file> [--job-glob <glob>]... [<pilot.json>]
#
# --job-glob selects job directories under --jobs-dir (default: all of them). The key file
# holds the key on one line; a file with a blank line is refused, because grep -f would then
# match every file. Exits 1 when any file contains the key or a key-shaped string.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" >&2; exit 2; }

JOBS_DIR="" KEY_FILE="" RECORDS=""
GLOBS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --jobs-dir) JOBS_DIR=${2:?}; shift 2 ;;
    --key-file) KEY_FILE=${2:?}; shift 2 ;;
    --job-glob) GLOBS+=("${2:?}"); shift 2 ;;
    -h|--help) usage ;;
    -*) echo "unknown option $1" >&2; usage ;;
    *) RECORDS=$1; shift ;;
  esac
done
[ -n "$JOBS_DIR" ] && [ -n "$KEY_FILE" ] || usage
[ -d "$JOBS_DIR" ] || { echo "no such jobs dir: $JOBS_DIR" >&2; exit 2; }
[ -r "$KEY_FILE" ] || { echo "cannot read the key file" >&2; exit 2; }
[ "$(grep -c '^$' "$KEY_FILE" || true)" = 0 ] || { echo "the key file has a blank line; refusing (grep -f would match everything)" >&2; exit 2; }
[ "${#GLOBS[@]}" -gt 0 ] || GLOBS=("*")

DIRS=()
shopt -s nullglob
for pattern in "${GLOBS[@]}"; do
  for dir in "$JOBS_DIR"/$pattern; do
    [ -d "$dir" ] && DIRS+=("$dir")
  done
done
shopt -u nullglob
[ "${#DIRS[@]}" -gt 0 ] || { echo "no job directory matches under $JOBS_DIR" >&2; exit 2; }

files=$(find "${DIRS[@]}" -type f | wc -l | tr -d ' ')
with_key=$( (grep -rlF -f "$KEY_FILE" "${DIRS[@]}" 2>/dev/null || true) | wc -l | tr -d ' ')
key_shaped=$( (grep -rlE 'sk-[A-Za-z0-9]{20,}' "${DIRS[@]}" 2>/dev/null || true) | wc -l | tr -d ' ')
echo "job dirs: ${#DIRS[@]}, regular files: $files"
echo "files containing the configured key: $with_key"
echo "files containing a key-shaped string: $key_shaped"

if [ -n "$RECORDS" ]; then
  python3 - "$RECORDS" <<'EOF'
import json, sys

with open(sys.argv[1], encoding="utf-8") as f:
    trials = json.load(f)["trials"]
ratios = []
for r in trials:
    p = r.get("pricing_usd_per_1m") or {}
    if not r.get("cost_usd") or not p:
        continue
    cache = r.get("n_cache_tokens") or 0
    write = (r.get("n_input_tokens") or 0) - cache
    peak = (cache * p["cache_read"] + write * p["cache_write"] + (r.get("n_output_tokens") or 0) * p["output"]) / 1e6
    if peak > 0:
        ratios.append((r["cost_usd"] / peak, r["job"], r["task"]))
ratios.sort()
if ratios:
    print(f"priced trials: {len(ratios)}; cost / peak price: min {ratios[0][0]:.4f} ({ratios[0][2]}), "
          f"max {ratios[-1][0]:.4f} ({ratios[-1][2]})")
else:
    print("priced trials: 0")
print("cost_complete false:", [(r["job"], r["task"]) for r in trials if r.get("cost_usd") is not None and not r.get("cost_complete")])
EOF
fi

[ "$with_key" = 0 ] && [ "$key_shaped" = 0 ]
