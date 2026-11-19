#!/bin/sh
LD_LIBRARY_PATH=/opt/task-legacy-libs:/usr/local/lib exec /opt/task-mongodb/bin/mongod "$@"
