#!/bin/sh
set -eu

export FORCE_COLOR=1
exec /usr/local/bin/node /opt/jest-runtime/node_modules/jest/bin/jest.js "$@"
