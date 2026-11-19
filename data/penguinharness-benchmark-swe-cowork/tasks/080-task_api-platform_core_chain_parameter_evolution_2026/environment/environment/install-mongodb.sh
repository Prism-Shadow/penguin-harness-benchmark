#!/bin/sh
set -eu

mongodb_version=2.4.0
installer_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
archive=$(python3 "$installer_dir/prepare-mongodb.py" --cache "${TASK_DEPENDENCY_CACHE:-/opt/task-environment/downloads}")
timeout --kill-after=30s 900s env MAKEFLAGS=-j2 pecl install "$archive"
docker-php-ext-enable mongodb
php -r 'exit(phpversion("mongodb") === $argv[1] ? 0 : 1);' -- "$mongodb_version"
