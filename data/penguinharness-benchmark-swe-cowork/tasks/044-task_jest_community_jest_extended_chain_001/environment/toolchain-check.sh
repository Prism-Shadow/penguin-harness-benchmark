#!/bin/sh
set -eu
. /etc/profile.d/cowork-toolchain.sh
cd /app/code
for tool in node eslint babel jest; do
    command -v "$tool"
done
/usr/local/bin/node -e 'for (const name of ["babel-register", "babel-plugin-transform-es2015-modules-commonjs", "babel-plugin-transform-object-rest-spread", "jest", "expect", "eslint"]) { const resolved = require.resolve(name); if (!resolved.startsWith("/opt/jest-runtime/node_modules/")) throw new Error("unexpected dependency: " + resolved); console.log(name + "=" + resolved); }'
eslint --version
babel --version
jest --version
