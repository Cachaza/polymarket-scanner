from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    generated_at: str
    db_age: str
    first_snapshot_ts: str | None
    latest_snapshot_ts: str | None
    markets_discovered: int
    active_scanner_scope: int
    markets_with_enough_6h_history: int
    markets_with_enough_24h_history: int
    markets_with_enough_72h_history: int
    watchlist_candidates: int
    alerts_count: int
    backtestable_alerts_6h: int
    backtestable_alerts_24h: int
    backtestable_alerts_72h: int
    latest_watchlist_snapshot_ts: str | None
    latest_backtest_ts: str | None


class MarketSummary(BaseModel):
    condition_id: str
    title: str
    market_id: str | None
    event_slug: str | None
    market_slug: str | None
    market_url: str | None
    category: str | None
    active: bool
    closed: bool
    accepting_orders: bool | None
    end_date: str | None
    latest_snapshot_ts: str | None
    current_yes_price: float | None
    yes_top5_seen_share: float | None
    observed_holder_wallets: int | None
    history_ready_6h: bool
    history_ready_24h: bool
    history_ready_72h: bool
    watchlist_flag: bool
    warmup_only: bool
    trade_enriched: bool
    latest_alert_ts: str | None
    latest_alert_severity: str | None


class MarketsResponse(BaseModel):
    total: int
    items: List[MarketSummary]


class WatchlistCandidateResponse(BaseModel):
    snapshot_ts: str
    condition_id: str
    market_title: str | None
    market_url: str | None
    current_yes_price: float | None
    price_delta_6h: float | None
    yes_top5_seen_share: float | None
    price_anomaly_hit: bool
    holder_concentration_hit: bool
    wallet_quality_hit: bool
    warmup_only: bool
    history_ready_6h: bool
    trade_enriched: bool
    reason_summary: str | None
    component_flags: Dict[str, Any]


class WatchlistResponse(BaseModel):
    snapshot_ts: str | None
    total: int
    items: List[WatchlistCandidateResponse]


class AlertResponse(BaseModel):
    id: int
    alert_ts: str
    condition_id: str
    market_title: str | None
    market_url: str | None
    alert_type: str
    score: float
    score_total: float
    score_price_anomaly: float
    score_holder_concentration: float
    score_wallet_quality: float
    score_trade_flow: float
    current_yes_price: float | None
    price_delta_6h: float | None
    price_delta_24h: float | None
    price_delta_72h: float | None
    severity: str | None
    confidence: str | None
    action_label: str | None
    reason_summary: str | None
    summary: str | None
    reasons: List[str]
    sent: bool


class AlertsResponse(BaseModel):
    total: int
    items: List[AlertResponse]


class MarketDetailResponse(BaseModel):
    condition_id: str
    title: str
    description: str | None
    category: str | None
    market_id: str | None
    question_id: str | None
    event_slug: str | None
    market_slug: str | None
    market_url: str | None
    active: bool
    closed: bool
    archived: bool
    accepting_orders: bool | None
    end_date: str | None
    closed_time: str | None
    yes_token_id: str | None
    no_token_id: str | None
    image_url: str | None
    reward_asset_address: str | None
    discovered_at: str | None
    last_seen_at: str | None
    current_yes_price: float | None
    current_no_price: float | None
    yes_top5_seen_share: float | None
    no_top5_seen_share: float | None
    observed_holder_wallets: int | None
    history_ready_6h: bool
    history_ready_24h: bool
    history_ready_72h: bool
    watchlist_flag: bool
    warmup_only: bool
    trade_enriched: bool
    recent_alert_count: int
    latest_alert_ts: str | None
    latest_alert_severity: str | None
    latest_watchlist_reason_summary: str | None


class TimeSeriesPoint(BaseModel):
    snapshot_ts: str
    yes_price: float | None
    no_price: float | None
    yes_top5_seen_share: float | None
    no_top5_seen_share: float | None
    observed_holder_wallets: int | None


class TimeSeriesResponse(BaseModel):
    condition_id: str
    hours: int
    items: List[TimeSeriesPoint]


class HolderResponse(BaseModel):
    snapshot_ts: str
    token_id: str
    wallet_address: str
    amount: float | None
    outcome_index: int | None
    rank: int | None
    politics_score: float | None
    overall_score: float | None
    politics_pnl_rank: int | None
    overall_pnl_rank: int | None


class HoldersResponse(BaseModel):
    condition_id: str
    snapshot_ts: str | None
    items: List[HolderResponse]


class TradeResponse(BaseModel):
    trade_key: str
    trade_ts: str
    wallet_address: str | None
    side: str | None
    outcome: str | None
    price: float | None
    size: float | None
    notional: float | None
    tx_hash: str | None
    title: str | None


class TradesResponse(BaseModel):
    condition_id: str
    total: int
    items: List[TradeResponse]


class TradeAftermathPoint(BaseModel):
    snapshot_ts: str
    yes_price: float | None
    no_price: float | None
    yes_top5_seen_share: float | None
    no_top5_seen_share: float | None
    observed_holder_wallets: int | None
    relative_hours: float | None


class TradeAftermathHorizon(BaseModel):
    target_hours: int
    snapshot_ts: str | None
    observed_hours_after_trade: float | None
    yes_price: float | None
    no_price: float | None
    yes_return: float | None
    no_return: float | None
    outcome_price: float | None
    outcome_return: float | None


class TradeAftermathTradeResponse(BaseModel):
    trade_key: str
    trade_ts: str
    wallet_address: str | None
    side: str | None
    outcome: str | None
    price: float | None
    size: float | None
    notional: float | None
    tx_hash: str | None
    title: str | None
    politics_score: float | None
    overall_score: float | None
    politics_pnl_rank: int | None
    overall_pnl_rank: int | None
    entry_snapshot_ts: str | None
    entry_snapshot_lag_minutes: float | None
    entry_yes_price: float | None
    entry_no_price: float | None
    current_snapshot_ts: str | None
    current_yes_price: float | None
    current_no_price: float | None
    current_yes_return: float | None
    current_no_return: float | None
    current_outcome_price: float | None
    current_outcome_return: float | None
    horizons: List[TradeAftermathHorizon]
    surrounding_points: List[TradeAftermathPoint]


class TradeAftermathResponse(BaseModel):
    condition_id: str
    total: int
    side: str | None
    outcome: str | None
    min_notional: float | None
    items: List[TradeAftermathTradeResponse]


class AggregateBucket(BaseModel):
    key: str
    count: int
    avg_return: float | None
    median_return: float | None
    positive_rate: float | None


class BacktestRowResponse(BaseModel):
    row: Dict[str, Any]


class BacktestResponse(BaseModel):
    csv_path: str
    exists: bool
    updated_at: str | None
    total_rows: int
    horizons: List[int]
    score_buckets: List[AggregateBucket]
    severity_buckets: List[AggregateBucket]
    confidence_buckets: List[AggregateBucket]
    alert_type_buckets: List[AggregateBucket]
    missing_reason_buckets: List[AggregateBucket]
    rows: List[Dict[str, Any]]


class JobRunResponse(BaseModel):
    id: int
    job_name: str
    started_at: str
    finished_at: str | None
    status: str
    rows_written: int | None
    meta: Dict[str, Any]
    error_text: str | None


class JobActionRequest(BaseModel):
    action: str
    hours: List[int] | None = None
    confirm_hours: int | None = None
    max_drift: float | None = None
    min_notional: float | None = None
    min_wallet_score: float | None = None


class JobActionResponse(BaseModel):
    job_name: str
    status: str
    rows_written: int | None
    meta: Dict[str, Any]
    output_path: str | None


class SystemResponse(BaseModel):
    overview: OverviewResponse
    backtest_csv_path: str
    backtest_exists: bool
    backtest_updated_at: str | None
    latent_backtest_csv_path: str
    latent_backtest_exists: bool
    latent_backtest_updated_at: str | None
    recent_job_runs: List[JobRunResponse]
