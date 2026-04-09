PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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
    title TEXT,
    description TEXT,
    category TEXT,
    active INTEGER,
    closed INTEGER,
    archived INTEGER,
    end_date TEXT,
    yes_token_id TEXT,
    no_token_id TEXT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
