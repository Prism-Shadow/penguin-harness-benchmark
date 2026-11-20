#!/usr/bin/env bash
set -Eeuo pipefail
node_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$node_dir/../common_behavior.sh" "$node_dir"
