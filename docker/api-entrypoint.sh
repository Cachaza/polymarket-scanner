#!/bin/sh
set -eu

mkdir -p "$(dirname "${POLY_DB_PATH:-/app/data/polymarket.sqlite}")"

attempt=1
until polymarket-scanner init-db; do
    if [ "$attempt" -ge 10 ]; then
        echo "Failed to initialize the database after ${attempt} attempts"
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
done

exec "$@"
