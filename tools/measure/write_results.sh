#!/usr/bin/env bash
# Writes the results of a measurement with tools/summarize.py.
#
#   tools/measure/write_results.sh --version v0.2.13 --jobs-dir <dir> --out <dir> --notes-file <file>
#       [--pilot-jobs <glob>]... [--pilot-balance <before.json> <after.json>]
#
# 1. With --pilot-jobs (shell globs of job names under --jobs-dir, e.g. "pilot-*"):
#    `summarize.py pilot` writes <out>/pilot/pilot.json from those jobs and prints its cut
#    helper. A matching job in which no trial finished (an interrupted run) is left out.
# 2. `summarize.py results` writes <out>/{summary.json,env.json,README.md,<benchmark>/attempt-<n>.json}
#    from the jobs <benchmark>-attempt-<n> and their reruns, with the balance readings
#    balance-attempt-<n>-{before,after}.json under --jobs-dir. With --pilot-jobs, attempt 1
#    is the pilot's trials of the final tasks (the v0.2.13 accounting, see attempt1_cost.py)
#    and pilot.json gives the pilot's cost; --pilot-balance names the readings around the
#    pilot.
#
# --notes-file holds the deviations and remarks for env.json and README.md, one per
# paragraph (blank-line separated; the lines of a paragraph are joined with single spaces).
# <out> must not exist yet, or be empty: the results are written whole.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" >&2; exit 2; }
die() { echo "write_results.sh: $*" >&2; exit 2; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
absolute() { case $1 in /*) echo "$1" ;; *) echo "$PWD/$1" ;; esac; }

VERSION="" JOBS_DIR="" OUT="" NOTES_FILE=""
PILOT_GLOBS=() BALANCE=()
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=${2:?}; shift 2 ;;
    --jobs-dir) JOBS_DIR=${2:?}; shift 2 ;;
    --out) OUT=${2:?}; shift 2 ;;
    --notes-file) NOTES_FILE=${2:?}; shift 2 ;;
    --pilot-jobs) PILOT_GLOBS+=("${2:?}"); shift 2 ;;
    --pilot-balance) BALANCE=(--pilot-balance "$(absolute "${2:?}")" "$(absolute "${3:?}")"); shift 3 ;;
    -h|--help) usage ;;
    *) echo "unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$VERSION" ] && [ -n "$JOBS_DIR" ] && [ -n "$OUT" ] && [ -n "$NOTES_FILE" ] || usage
[ -d "$JOBS_DIR" ] || die "no such jobs dir: $JOBS_DIR"
[ -r "$NOTES_FILE" ] || die "cannot read the notes file: $NOTES_FILE"
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT")" ]; then die "$OUT is not empty; results are written whole"; fi
JOBS_DIR=$(absolute "$JOBS_DIR") OUT=$(absolute "$OUT") NOTES_FILE=$(absolute "$NOTES_FILE")

NOTES=()
while IFS= read -r -d '' note; do NOTES+=(--note "$note"); done < <(python3 -c '
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
for paragraph in re.split(r"\n[ \t]*\n", text):
    if paragraph.strip():
        sys.stdout.write(" ".join(paragraph.split()) + "\0")' "$NOTES_FILE")

cd "$ROOT"
mkdir -p "$OUT"
PILOT=()
if [ "${#PILOT_GLOBS[@]}" -gt 0 ]; then
  PILOT_DIRS=()
  shopt -s nullglob
  for pattern in "${PILOT_GLOBS[@]}"; do
    for dir in "$JOBS_DIR"/$pattern; do
      [ -d "$dir" ] || continue
      [[ " ${PILOT_DIRS[*]-} " == *" $dir "* ]] && continue
      finished=("$dir"/*/result.json)
      if [ "${#finished[@]}" = 0 ]; then echo "left out $(basename "$dir"): no finished trial" >&2; continue; fi
      PILOT_DIRS+=("$dir")
    done
  done
  shopt -u nullglob
  [ "${#PILOT_DIRS[@]}" -gt 0 ] || die "no pilot job matches ${PILOT_GLOBS[*]} under $JOBS_DIR"
  mkdir -p "$OUT/pilot"
  python3 tools/summarize.py pilot --out "$OUT/pilot/pilot.json" "${PILOT_DIRS[@]}"
  PILOT=(--pilot "$OUT/pilot/pilot.json" --attempt1-pilot "${PILOT_DIRS[@]}")
fi
python3 tools/summarize.py results --version "$VERSION" --jobs-dir "$JOBS_DIR" --out "$OUT" \
  ${PILOT[@]+"${PILOT[@]}"} ${BALANCE[@]+"${BALANCE[@]}"} ${NOTES[@]+"${NOTES[@]}"}
find "$OUT" -type f | sort
