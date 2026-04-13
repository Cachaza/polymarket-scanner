# Polymarket anomaly scanner (starter repo)

Cheap first-pass scanner for **US / politics / geopolitics** markets on Polymarket.

It is designed for:
- polling every 10–30 minutes,
- low infra cost,
- wallet/holder anomaly detection,
- light backtesting from your stored snapshots.

It uses only public Polymarket APIs for market discovery, holders, trades, leaderboard data, and public CLOB price reads. Polymarket documents the Gamma API for events/markets, the public Data API for holders/trades/leaderboards, and public CLOB endpoints for last-trade prices and price history. It also recommends using the **events** endpoint for complete active-market discovery because events already include their associated markets. citeturn937239search0turn311943view6turn931090view0turn931090view1turn101383view0turn101383view1

## What this repo does

- discovers active events and markets
- filters markets by keywords
- stores market metadata, wallet scores, holder snapshots, price snapshots, trade enrichments, and alerts in SQLite
- uses **batch CLOB last-trade price** fetches so snapshots stay cheap
- only fetches recent trades for candidate markets that already look interesting
- runs a coarse backtest over stored alerts and snapshots

## Why this architecture is better than the first rough sketch

A few improvements over the earlier design:

1. **Use `/events` for discovery, not `/markets`.**  
   Polymarket’s docs explicitly say the events endpoint is the most efficient way to retrieve active markets because events contain their associated markets. citeturn311943view6turn206104view0

2. **Use batch last-trade prices from CLOB instead of one price call per market.**  
   The public `GET /last-trades-prices` endpoint supports up to 500 token IDs per request, which is ideal for cheap polling. citeturn101383view0

3. **Do not fetch trades for every market on every cycle.**  
   The scanner first snapshots prices + holders, then fetches `/trades` only for short-listed candidate markets. The Data API trade endpoint is public, but this selective enrichment is much cheaper and still aligned with your hours-to-days horizon. citeturn311943view4

4. **Be careful with concentration math.**  
   The top holders endpoint is capped at 20 holders per token, so any “concentration” metric is only a share of the observed top-N holders, not the true full-holder distribution. This repo names that field `*_top5_seen_share` to avoid fake precision. citeturn931090view0

5. **Keep wallet novelty honest.**  
   “New wallet” here means “new to your database,” not necessarily newly created on-chain.

6. **Keep suspicion language out of the code.**  
   The repo treats this as an **anomaly / smart-money scanner**. That framing is both more defensible and easier to validate.

## Current limitations

- historical backtests are only as good as the history you stored or can backfill
- wallet identity is unknown; the code detects patterns, not insiders
- holder concentration is approximate because top holders are capped
- prices use last-trade snapshots, not full order-book microstructure
- keyword filtering is crude by default

## High-impact improvements I would make next

1. **Tag-first discovery**
   - use event or market tags to reduce keyword false positives before falling back to keywords  
   Polymarket supports `tag_id`, `tag_slug`, and related tag filters on discovery endpoints. citeturn206104view0turn931090view3

2. **Add public news overlap suppression**
   - integrate a simple RSS/news layer later so the bot can lower alert scores when public news already explains the move

3. **Use `prices-history` for backfill / richer backtests**
   - the public CLOB `GET /prices-history` endpoint supports intervals like `1h`, `6h`, and `1d`, which fits your slow-horizon use case. citeturn101383view1

4. **Separate wallet skill into category-specific and recency-specific scores**
   - politics `ALL` and politics `MONTH` are probably more useful than only one leaderboard snapshot  
   Polymarket’s leaderboard supports categories like `POLITICS` and periods `DAY`, `WEEK`, `MONTH`, and `ALL`. citeturn931090view1

5. **Shortlist by event volume before enrichment**
   - only enrich markets above a minimum `volume24hr` or `openInterest` threshold

6. **Add paper-trading before any execution**
   - if you ever automate trading later, use the official Python client / trading auth flow rather than hand-rolling signing  
   Polymarket documents official clients and separate trading auth requirements for CLOB order endpoints. citeturn937239search11turn486785search8

## Setup

```bash
uv sync
cp .env.example .env
uv run polymarket-scanner init-db
```

If you prefer the module form, use `uv run python -m app ...`.

## Scanner Console

This repo now includes a local read-only scanner console:

- a small FastAPI layer over the SQLite database
- a Next.js app in `web/`
- persisted `watchlist_candidates` history
- persisted `recommendations` history
- tracked `job_runs` for discover / refresh / snapshot / score-alerts / backtest

### Start the API

```bash
uv run polymarket-scanner-api
```

The API serves these read endpoints under `/api/v1`:

- `/overview`
- `/markets`
- `/watchlist`
- `/alerts`
- `/recommendations`
- `/markets/{condition_id}`
- `/markets/{condition_id}/timeseries`
- `/markets/{condition_id}/holders`
- `/markets/{condition_id}/trades`
- `/markets/{condition_id}/trade-aftermath`
- `/research/backtests`
- `/research/latent-backtests`
- `/system`

The system UI also exposes local action endpoints so you can trigger selected jobs from the dashboard:

- `POST /system/actions/run`

### Start the web app

```bash
cd web
nvm use
npm install
SCANNER_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://127.0.0.1:3000`.

The frontend is intended to run on Node `24.x` LTS. A `.nvmrc` file is included in `web/` so `nvm use` will select the right version.

When running against the live API, `SCANNER_API_BASE_URL` is the internal destination used by the Next.js rewrite. Browser requests go through `/scanner-api`, so the frontend still works correctly inside Docker and behind Dokploy.

### Mock mode for frontend work

If you want to work on the UI without the Python API running:

```bash
cd web
nvm use
npm install
NEXT_PUBLIC_SCANNER_API_MODE=mock npm run dev
```

### Frontend checks

```bash
cd web
npm run typecheck
npm run lint
```

### Python checks

```bash
uv run pytest
```

## Commands

```bash
uv run polymarket-scanner discover
uv run polymarket-scanner refresh-leaderboard
uv run polymarket-scanner snapshot
uv run polymarket-scanner score-alerts
uv run polymarket-scanner backtest --hours 24
uv run polymarket-scanner latent-backtest --hours 24 72 120 --confirm-hours 24 --max-drift 0.05 --min-notional 1000 --min-wallet-score 60
uv run polymarket-scanner run-cycle
```

## Suggested cron schedule

```cron
# discover markets every 6 hours
0 */6 * * *  cd /path/to/polymarket_scanner && .venv/bin/polymarket-scanner discover

# refresh wallet leaderboard daily
15 2 * * *   cd /path/to/polymarket_scanner && .venv/bin/polymarket-scanner refresh-leaderboard

# snapshot every 15 minutes
*/15 * * * * cd /path/to/polymarket_scanner && .venv/bin/polymarket-scanner snapshot

# score alerts every 15 minutes, a minute later
1-59/15 * * * * cd /path/to/polymarket_scanner && .venv/bin/polymarket-scanner score-alerts
```

## Docker / Dokploy

The repo now includes:

- a backend image for the FastAPI API and CLI jobs
- a frontend image for the Next.js console
- a worker service that runs the scheduled scanner jobs inside the same Compose stack
- a named Docker volume for the SQLite database and CSV outputs

### Local Compose

```bash
cp .env.example .env
docker compose up --build -d
```

The web UI is exposed on `http://localhost:3000` by default. The backend API stays internal to the Compose network and is reached by the frontend through `/scanner-api`.

The default worker schedules match the README cron examples and can be overridden from `.env` with:

- `POLY_DISCOVER_CRON`
- `POLY_REFRESH_LEADERBOARD_CRON`
- `POLY_SNAPSHOT_CRON`
- `POLY_SCORE_ALERTS_CRON`

### Dokploy

Use the repository as a Docker Compose application and expose only the `web` service.

Recommended Dokploy setup:

- copy `.env.example` to `.env` and fill in any Polymarket / Telegram settings you need
- keep the `scanner_data` volume persistent so SQLite and CSV outputs survive redeploys
- route your public domain to the `web` service on port `3000`
- leave `api` and `worker` private on the internal Compose network

## Notes on rate limits

Polymarket’s docs currently show very high general public rate limits enforced by Cloudflare, but this repo still keeps calls modest because lower call counts are cheaper, simpler, and easier to reason about. citeturn311943view3
