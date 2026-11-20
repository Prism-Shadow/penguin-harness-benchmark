#!/usr/bin/env bash
set -Eeuo pipefail

repo="${REPO_DIR:-/workspace}"
find "$repo" -mindepth 1 -maxdepth 1 ! -name vendor -exec rm -rf -- {} +
tar -xf /solution/gold-tree.tar -C "$repo"
