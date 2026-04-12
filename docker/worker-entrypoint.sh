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

cat > /tmp/polymarket-scanner.cron <<EOF
${POLY_DISCOVER_CRON:-0 */6 * * *} /usr/local/bin/run-locked-job.sh discover
${POLY_REFRESH_LEADERBOARD_CRON:-15 2 * * *} /usr/local/bin/run-locked-job.sh refresh-leaderboard
${POLY_SNAPSHOT_CRON:-*/15 * * * *} /usr/local/bin/run-locked-job.sh snapshot
${POLY_SCORE_ALERTS_CRON:-1-59/15 * * * *} /usr/local/bin/run-locked-job.sh score-alerts
EOF

echo "Loaded worker schedule:"
cat /tmp/polymarket-scanner.cron

exec /usr/local/bin/supercronic /tmp/polymarket-scanner.cron
