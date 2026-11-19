#!/bin/sh
set -eu
sh /run/row077-prepare-runtime.sh
exec "$@"
