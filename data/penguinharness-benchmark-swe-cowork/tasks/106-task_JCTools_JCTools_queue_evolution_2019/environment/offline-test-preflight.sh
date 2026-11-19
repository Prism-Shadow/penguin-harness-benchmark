#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_DIR:-/app/code}"
exec mvn -o -B -T 2 -pl jctools-core -am \
    -Dtest=Pow2Test -Dsurefire.failIfNoSpecifiedTests=false -Dexec.skip=true test
