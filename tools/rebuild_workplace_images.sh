#!/usr/bin/env bash
# Rebuild the SWE-CoWork `workplace` images so that edits under a task's
# `environment/workplace-code/` actually take effect at run time.
#
# Why this exists
# ---------------
# The task's docker-compose.yaml references the workplace service by image tag
# only (`image: 002-workplace:002-workplace`) and has no `build:` section. The
# `runtime-files.json` file in the environment directory declares a host->container
# mapping, but nothing in Harbor reads it. The consequence is that the Python
# files on the host are inert: editing them changes nothing, and every run keeps
# executing whatever was baked into the image when it was built.
#
# This script derives a `*-fixed` image from the existing one, overwriting only
# the four files that make up the service, then repoints the compose file at it.
# It is deliberately a derive-and-overwrite build rather than a full rebuild so
# that the base layers (interpreter, entrypoint, helper modules that live only in
# the image) are preserved.
#
# Usage
#   ./rebuild_workplace_images.sh                 # all tasks found under --tasks-root
#   ./rebuild_workplace_images.sh 002             # only matching task prefixes
#   ./rebuild_workplace_images.sh --verify-only   # assert the fix is inside the image
#
# Remote execution (the images live on the experiment host, not here)
#   SSH_HOST=root@21.6.124.161 SSH_PORT=36000 ./rebuild_workplace_images.sh 002
#
# Environment
#   SSH_HOST     if set, the build runs on that host over ssh
#   SSH_PORT     ssh port (default 22)
#   TASKS_ROOT   remote/local task directory (default /data/swe-cowork/job/tasks)
#   PYTHON       interpreter used for the in-image verification (default python3)

set -euo pipefail

SSH_HOST="${SSH_HOST:-}"
SSH_PORT="${SSH_PORT:-22}"
TASKS_ROOT="${TASKS_ROOT:-/data/swe-cowork/job/tasks}"
PYTHON="${PYTHON:-python3}"

VERIFY_ONLY=0
PREFIXES=()
for arg in "$@"; do
  case "$arg" in
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) PREFIXES+=("$arg") ;;
  esac
done

# Run a command either locally or on the experiment host.
run() {
  if [ -n "$SSH_HOST" ]; then
    # shellcheck disable=SC2029  # word splitting of $1 is intentional (whole snippet)
    ssh -p "$SSH_PORT" -o ConnectTimeout=20 "$SSH_HOST" "$1"
  else
    bash -c "$1"
  fi
}

# The four files that constitute the workplace service. `workplace_sidecar.py`
# is renamed to `workplace-sidecar` in the image, matching the base image layout.
SERVICE_FILES="semantic_colleague.py harbor_dynamic_colleague_adapter.py runtime_daemon.py workplace-sidecar"

TMP_DOCKERFILE="$(mktemp)"
trap 'rm -f "$TMP_DOCKERFILE"' EXIT

# Every one of the 101 tasks ships a `workplace-code/` tree, but only the tasks
# actually being worked on have had the fix applied to it. Requiring the fix to be
# present keeps the default run focused: an unpatched task has nothing to rebuild,
# and silently deriving a `*-fixed` image from identical sources would suggest a
# change that did not happen.
selected_dirs() {
  local found
  found="$(run "for d in $TASKS_ROOT/*/environment; do
      [ -f \"\$d/workplace-code/semantic_colleague.py\" ] || continue
      grep -q 'resolve_max_output_tokens' \"\$d/workplace-code/semantic_colleague.py\" || continue
      base=\$(basename \"\$(dirname \"\$d\")\")
      for p in ${PREFIXES[*]:-ALL}; do
        if [ \"\$p\" = ALL ] || printf '%s' \"\$base\" | grep -q \"^\$p\"; then
          echo \"\$d\"; break
        fi
      done
    done")"
  printf '%s\n' "$found"
}

verify_image() {
  local tag="$1"
  run "docker run --rm --entrypoint sh $tag -c '
    grep -n \"DEFAULT_MAX_OUTPUT_TOKENS =\|MAX_OUTPUT_TOKENS_ENV =\" /usr/local/bin/semantic_colleague.py
    grep -c \"def resolve_max_output_tokens\" /usr/local/bin/semantic_colleague.py
  '" || return 1
}

n_ok=0
n_fail=0
for env_dir in $(selected_dirs); do
  [ -n "$env_dir" ] || continue
  task_name="$(basename "$(dirname "$env_dir")")"
  prefix="${task_name:0:3}"
  base_image="${prefix}-workplace:${prefix}-workplace"
  fixed_image="${prefix}-workplace:${prefix}-workplace-fixed"

  echo "=== $task_name ==="

  if [ "$VERIFY_ONLY" -eq 1 ]; then
    if verify_image "$fixed_image"; then
      echo "    OK   $fixed_image contains the fix"
      n_ok=$((n_ok + 1))
    else
      echo "    FAIL $fixed_image is missing the fix"
      n_fail=$((n_fail + 1))
    fi
    continue
  fi

  # Fail loudly if the code directory does not carry the fix: building an image
  # from stale sources is the exact failure this script exists to prevent.
  if ! run "grep -q 'resolve_max_output_tokens' $env_dir/workplace-code/semantic_colleague.py"; then
    echo "    SKIP workplace-code/semantic_colleague.py does not define resolve_max_output_tokens()"
    n_fail=$((n_fail + 1))
    continue
  fi

  cat > "$TMP_DOCKERFILE" <<EOF
FROM $base_image
USER root
COPY semantic_colleague.py /usr/local/bin/semantic_colleague.py
COPY harbor_dynamic_colleague_adapter.py /usr/local/bin/harbor_dynamic_colleague_adapter.py
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY workplace-sidecar /usr/local/bin/workplace-sidecar
RUN chmod 0444 /usr/local/bin/semantic_colleague.py /usr/local/bin/harbor_dynamic_colleague_adapter.py /usr/local/bin/runtime_daemon.py \\
 && chmod 0555 /usr/local/bin/workplace-sidecar
EOF

  dockerfile_remote="/tmp/Dockerfile.rebuild.${prefix}"
  if [ -n "$SSH_HOST" ]; then
    scp -P "$SSH_PORT" -o ConnectTimeout=20 -q "$TMP_DOCKERFILE" "${SSH_HOST}:${dockerfile_remote}"
  else
    cp "$TMP_DOCKERFILE" "$dockerfile_remote"
  fi

  if ! run "cd $env_dir/workplace-code && docker build -f $dockerfile_remote -t $fixed_image . 2>&1 | tail -3"; then
    echo "    FAIL build failed"
    n_fail=$((n_fail + 1))
    continue
  fi

  if ! verify_image "$fixed_image"; then
    echo "    FAIL built image does not contain the fix"
    n_fail=$((n_fail + 1))
    continue
  fi
  echo "    OK   built and verified $fixed_image"

  # Repoint the compose file. Without this step the rebuilt image is simply never
  # used, which is just as silent as not rebuilding at all.
  run "cd $env_dir && \
       [ -f docker-compose.yaml.imagefix.bak ] || cp docker-compose.yaml docker-compose.yaml.imagefix.bak && \
       sed -i 's|image: $base_image\$|image: $fixed_image|' docker-compose.yaml && \
       grep -q '$fixed_image' docker-compose.yaml && echo '    OK   compose repointed'"
  n_ok=$((n_ok + 1))
done

echo
echo "done: $n_ok ok, $n_fail failed"
[ "$n_fail" -eq 0 ]
