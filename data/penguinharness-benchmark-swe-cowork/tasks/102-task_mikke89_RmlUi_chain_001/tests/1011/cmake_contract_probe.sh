#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/../1003/cmake_contract_probe.sh" "$@"
