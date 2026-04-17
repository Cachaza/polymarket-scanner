-- PostgreSQL schema for polymarket-scanner

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    slug TEXT,
    title TEXT,
    description TEXT,
    category TEXT,
    subcategory TEXT,
    active INTEGER,
    closed INTEGER,
    archived INTEGER,
    liquidity REAL,
    volume REAL,
    volume24hr REAL,
    open_interest REAL,
    end_date TEXT,
    updated_at TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS markets (
    condition_id TEXT PRIMARY KEY,
    event_id TEXT,
    event_slug TEXT,
    slug TEXT,
    market_id TEXT,
    question_id TEXT,
    market_url TEXT,
    title TEXT,
    description TEXT,
    category TEXT,
    active INTEGER,
    closed INTEGER,
    archived INTEGER,
    accepting_orders INTEGER,
    end_date TEXT,
    closed_time TEXT,
    yes_token_id TEXT,
    no_token_id TEXT,
    image_url TEXT,
    reward_asset_address TEXT,
    discovered_at TEXT,
    last_seen_at TEXT,
    raw_json TEXT,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);

CREATE INDEX IF NOT EXISTS idx_markets_active ON markets(active, closed);
CREATE INDEX IF NOT EXISTS idx_markets_event ON markets(event_id);

CREATE TABLE IF NOT EXISTS wallet_scores (
    wallet_address TEXT PRIMARY KEY,
    first_seen_ts TEXT,
    last_seen_ts TEXT,
    politics_pnl_rank INTEGER,
    politics_vol_rank INTEGER,
    overall_pnl_rank INTEGER,
    overall_vol_rank INTEGER,
    politics_score REAL,
    overall_score REAL,
    notes TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS wallet_score_history (
    id SERIAL PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    snapshot_ts TEXT NOT NULL,
    category TEXT NOT NULL,
    time_period TEXT NOT NULL,
    order_by TEXT NOT NULL,
    rank INTEGER,
    score_value REAL,
    raw_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_score_history_unique
ON wallet_score_history(wallet_address, snapshot_ts, category, time_period, order_by);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    condition_id TEXT NOT NULL,
    snapshot_ts TEXT NOT NULL,
    yes_price REAL,
    no_price REAL,
    yes_side TEXT,
    no_side TEXT,
    yes_holder_count INTEGER,
    no_holder_count INTEGER,
    yes_top_holder_amount REAL,
    no_top_holder_amount REAL,
    yes_top5_seen_share REAL,
    no_top5_seen_share REAL,
    observed_holder_wallets INTEGER,
    raw_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_snapshots_unique
ON market_snapshots(condition_id, snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_condition_ts
ON market_snapshots(condition_id, snapshot_ts);

CREATE TABLE IF NOT EXISTS holder_snapshots (
    id SERIAL PRIMARY KEY,
    condition_id TEXT NOT NULL,
    snapshot_ts TEXT NOT NULL,
    token_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    amount REAL,
    outcome_index INTEGER,
    rank INTEGER,
    raw_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_holder_snapshots_unique
ON holder_snapshots(condition_id, snapshot_ts, token_id, wallet_address);

CREATE TABLE IF NOT EXISTS trades (
    trade_key TEXT PRIMARY KEY,
    trade_ts TEXT NOT NULL,
    condition_id TEXT,
    token_id TEXT,
    wallet_address TEXT,
    side TEXT,
    price REAL,
    size REAL,
    notional REAL,
    tx_hash TEXT,
    title TEXT,
    outcome TEXT,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_condition_ts
ON trades(condition_id, trade_ts);

CREATE INDEX IF NOT EXISTS idx_trades_wallet_ts
ON trades(wallet_address, trade_ts);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_ts TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    score REAL NOT NULL,
    score_total REAL NOT NULL DEFAULT 0,
    score_price_anomaly REAL NOT NULL DEFAULT 0,
    score_holder_concentration REAL NOT NULL DEFAULT 0,
    score_wallet_quality REAL NOT NULL DEFAULT 0,
    score_trade_flow REAL NOT NULL DEFAULT 0,
    market_title TEXT,
    market_url TEXT,
    yes_token_id TEXT,
    current_yes_price REAL,
    price_delta_6h REAL,
    price_delta_24h REAL,
    price_delta_72h REAL,
    severity TEXT,
    confidence TEXT,
    action_label TEXT,
    reason_summary TEXT,
    summary TEXT,
    reasons_json TEXT,
    sent INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(alert_ts);
CREATE INDEX IF NOT EXISTS idx_alerts_condition_ts ON alerts(condition_id, alert_ts);

CREATE TABLE IF NOT EXISTS watchlist_candidates (
    id SERIAL PRIMARY KEY,
    snapshot_ts TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    market_title TEXT,
    side TEXT NOT NULL DEFAULT 'Yes',
    current_yes_price REAL,
    current_no_price REAL,
    price_delta_6h REAL,
    no_price_delta_6h REAL,
    yes_top5_seen_share REAL,
    no_top5_seen_share REAL,
    price_anomaly_hit INTEGER NOT NULL DEFAULT 0,
    holder_concentration_hit INTEGER NOT NULL DEFAULT 0,
    wallet_quality_hit INTEGER NOT NULL DEFAULT 0,
    warmup_only INTEGER NOT NULL DEFAULT 0,
    history_ready_6h INTEGER NOT NULL DEFAULT 0,
    trade_enriched INTEGER NOT NULL DEFAULT 0,
    reason_summary TEXT,
    component_flags_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_candidates_unique
ON watchlist_candidates(condition_id, snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_watchlist_candidates_snapshot_ts
ON watchlist_candidates(snapshot_ts);

CREATE INDEX IF NOT EXISTS idx_watchlist_candidates_condition_ts
ON watchlist_candidates(condition_id, snapshot_ts);

CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    entry_ts TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    source TEXT NOT NULL,
    market_title TEXT,
    market_url TEXT,
    side TEXT NOT NULL DEFAULT 'Yes',
    recommendation TEXT NOT NULL,
    status TEXT NOT NULL,
    conviction_score REAL NOT NULL DEFAULT 0,
    severity TEXT,
    confidence TEXT,
    reason_summary TEXT,
    entry_price REAL,
    entry_yes_price REAL,
    history_ready_6h INTEGER NOT NULL DEFAULT 0,
    warmup_only INTEGER NOT NULL DEFAULT 0,
    trade_enriched INTEGER NOT NULL DEFAULT 0,
    source_meta_json TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_recommendations_unique
ON recommendations(condition_id, source, entry_ts);

CREATE INDEX IF NOT EXISTS idx_recommendations_condition_ts
ON recommendations(condition_id, entry_ts DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_source_ts
ON recommendations(source, entry_ts DESC);

CREATE TABLE IF NOT EXISTS job_runs (
    id SERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    rows_written INTEGER,
    meta_json TEXT,
    error_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_runs_name_started
ON job_runs(job_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_status_started
ON job_runs(status, started_at DESC);
