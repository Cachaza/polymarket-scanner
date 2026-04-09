from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .backtest import DEFAULT_BACKTEST_HORIZONS
from .config import Settings
from .db import Database
from .jobs.snapshot import (
    _passes_holder_concentration,
    _passes_price_anomaly,
    _passes_wallet_quality,
)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _parse_db_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _format_age(first_snapshot_ts: str | None) -> str:
    first_dt = _parse_db_ts(first_snapshot_ts)
    if first_dt is None:
        return "n/a"
    delta = datetime.now(timezone.utc) - first_dt
    total_seconds = max(0, int(delta.total_seconds()))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


def _count_watchlist_candidates(settings: Settings, db: Database) -> int:
    active_markets = db.get_active_markets(limit=settings.market_limit)
    latest_snapshots: Dict[str, Dict[str, Any]] = {}
    latest_holder_wallets: Dict[str, list[str]] = {}
    all_wallets = set()

    for market in active_markets:
        condition_id = market["condition_id"]
        latest_snapshot = db.get_latest_snapshot(condition_id)
        if not latest_snapshot:
            continue
        latest_snapshots[condition_id] = _row_to_dict(latest_snapshot)
        latest_holders = db.get_latest_holder_addresses(condition_id)
        latest_holder_wallets[condition_id] = latest_holders
        all_wallets.update(latest_holders)

    wallet_scores = db.get_wallet_scores(sorted(all_wallets))
    watchlist_count = 0

    for market in active_markets:
        condition_id = market["condition_id"]
        latest_snapshot = latest_snapshots.get(condition_id)
        if not latest_snapshot:
            continue
        prev_snapshot = db.get_snapshot_before(condition_id, latest_snapshot["snapshot_ts"], 6)
        prev_snapshot_dict = _row_to_dict(prev_snapshot) if prev_snapshot else None
        price_anomaly_pass = _passes_price_anomaly(latest_snapshot, prev_snapshot_dict)
        holder_concentration_pass = _passes_holder_concentration(latest_snapshot, prev_snapshot_dict)
        wallet_quality_pass = _passes_wallet_quality(latest_holder_wallets.get(condition_id, []), wallet_scores)
        if price_anomaly_pass or holder_concentration_pass or wallet_quality_pass:
            watchlist_count += 1

    return watchlist_count


def render_diagnostics(settings: Settings, db: Database) -> str:
    snapshot_bounds = db.get_snapshot_bounds()
    first_snapshot_ts = snapshot_bounds["first_snapshot_ts"] if snapshot_bounds else None
    latest_snapshot_ts = snapshot_bounds["latest_snapshot_ts"] if snapshot_bounds else None

    active_markets = db.get_active_markets(limit=settings.market_limit)
    active_condition_ids = [row["condition_id"] for row in active_markets]
    alerts = db.get_alerts()

    lines = [
        f"DB age: {_format_age(first_snapshot_ts)}",
        f"First snapshot: {first_snapshot_ts or 'n/a'}",
        f"Latest snapshot: {latest_snapshot_ts or 'n/a'}",
        f"Markets discovered: {db.get_market_count()}",
        f"Active scanner scope: {len(active_markets)}",
        f"Markets with enough 6h history: {db.count_history_ready_markets(active_condition_ids, 6)}",
        f"Markets with enough 24h history: {db.count_history_ready_markets(active_condition_ids, 24)}",
        f"Markets with enough 72h history: {db.count_history_ready_markets(active_condition_ids, 72)}",
        f"Watchlist candidates: {_count_watchlist_candidates(settings, db)}",
        f"Alerts count: {len(alerts)}",
    ]
    for hours in DEFAULT_BACKTEST_HORIZONS:
        lines.append(
            f"Backtestable alerts {hours}h: {db.count_backtestable_alerts(hours)}"
        )
    return "\n".join(lines)
