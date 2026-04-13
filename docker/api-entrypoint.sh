#!/bin/sh
set -eu

mkdir -p "$(dirname "${POLY_DB_PATH:-/app/data/polymarket.sqlite}")"

max_attempts="${POLY_DB_INIT_MAX_ATTEMPTS:-30}"
retry_delay="${POLY_DB_INIT_RETRY_DELAY_SECONDS:-2}"
attempt=1
until polymarket-scanner init-db; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Failed to initialize the database after ${attempt} attempts"
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep "$retry_delay"
done

exec "$@"
