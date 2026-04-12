#!/bin/sh
set -eu

job="$1"
shift

lock_file="${POLY_JOB_LOCK_FILE:-/tmp/polymarket-scanner.lock}"

if /usr/bin/flock -n -E 200 "$lock_file" /usr/local/bin/polymarket-scanner "$job" "$@"; then
    exit 0
fi

status="$?"

if [ "$status" -eq 200 ]; then
    echo "Skipped ${job}: another scanner job is still running"
    exit 0
fi

exit "$status"
