#!/bin/sh
set -eu
cd /app/code
patch --batch --forward -p1 < /solution/solution.patch
