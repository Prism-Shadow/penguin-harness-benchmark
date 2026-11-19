#!/bin/sh
set -eu
cd /workspace
patch --batch --forward -p1 < /solution/solution.patch
