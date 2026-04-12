from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .backtest import DEFAULT_BACKTEST_HORIZONS
from .config import Settings
from .db import Database


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


def _count_watchlist_candidates(db: Database) -> int:
    latest_row = db.conn.execute("SELECT MAX(snapshot_ts) AS snapshot_ts FROM watchlist_candidates").fetchone()
    latest_snapshot_ts = latest_row["snapshot_ts"] if latest_row else None
    if not latest_snapshot_ts:
        return 0
    count_row = db.conn.execute(
        "SELECT COUNT(*) AS n FROM watchlist_candidates WHERE snapshot_ts = ?",
        (latest_snapshot_ts,),
    ).fetchone()
    return int(count_row["n"]) if count_row else 0


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
        f"Watchlist candidates: {_count_watchlist_candidates(db)}",
        f"Alerts count: {len(alerts)}",
    ]
    for hours in DEFAULT_BACKTEST_HORIZONS:
        lines.append(
            f"Backtestable alerts {hours}h: {db.count_backtestable_alerts(hours)}"
        )
    return "\n".join(lines)
