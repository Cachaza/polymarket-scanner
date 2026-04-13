from __future__ import annotations

from bisect import bisect_left, bisect_right
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row

from .api_models import (
    AggregateBucket,
    AlertResponse,
    AlertsResponse,
    BacktestResponse,
    HolderResponse,
    HoldersResponse,
    JobRunResponse,
    MarketDetailResponse,
    MarketsResponse,
    MarketSummary,
    OverviewResponse,
    RecommendationItemResponse,
    RecommendationsResponse,
    SystemResponse,
    TradeAftermathHorizon,
    TradeAftermathPoint,
    TradeAftermathResponse,
    TradeAftermathTradeResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
    TradeResponse,
    TradesResponse,
    WatchlistCandidateResponse,
    WatchlistResponse,
)
from .backtest import DEFAULT_BACKTEST_HORIZONS, DEFAULT_LATENT_BACKTEST_HORIZONS
from .config import Settings
from .recommendations import outcome_verdict, recommendation_meta, resolved_yes_price
from .utils import build_market_url, utc_now_iso

# Type alias for a psycopg connection used in read-only queries
PgConn = psycopg.Connection


def _parse_db_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if str(value).isdigit():
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        normalized = str(value).replace(" ", "T")
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


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


def _row_to_dict(row: Dict[str, Any] | None) -> Dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _normalize_alert_reasons(value: str | None) -> List[str]:
    payload = _json_loads(value, [])
    if isinstance(payload, list):
        return [str(item) for item in payload]
    if isinstance(payload, dict):
        reasons = payload.get("reasons")
        if isinstance(reasons, list):
            return [str(item) for item in reasons]
        reason_summary = payload.get("reason_summary")
        if reason_summary:
            return [str(reason_summary)]
        return []
    return []


def _file_updated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _pct_change(entry: float | None, exit_value: float | None) -> float | None:
    if entry in (None, 0) or exit_value is None:
        return None
    return round((exit_value - entry) / entry, 4)


def _round_hours(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _round_minutes(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def _latest_watchlist_snapshot_ts(conn: PgConn) -> str | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT MAX(snapshot_ts) AS snapshot_ts FROM watchlist_candidates")
        row = cur.fetchone()
        return row["snapshot_ts"] if row else None


def _scanner_scope_cte() -> str:
    return """
    WITH scanner_scope AS (
        SELECT *
        FROM markets
        WHERE active = 1 AND closed = 0
        ORDER BY ctid DESC
        LIMIT %(market_limit)s
    )
    """


def _history_ready_count(conn: PgConn, *, market_limit: int, hours: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            {_scanner_scope_cte()},
            latest AS (
                SELECT ms.condition_id, MAX(ms.snapshot_ts) AS latest_snapshot_ts
                FROM market_snapshots ms
                JOIN scanner_scope s ON s.condition_id = ms.condition_id
                GROUP BY ms.condition_id
            )
            SELECT COUNT(*) AS n
            FROM latest
            WHERE EXISTS (
                SELECT 1
                FROM market_snapshots ms
                WHERE ms.condition_id = latest.condition_id
                  AND ms.snapshot_ts <= (latest.latest_snapshot_ts::timestamp - interval '1 hour' * %(hours)s)::text
            )
            """,
            {"market_limit": market_limit, "hours": hours},
        )
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def _overview_payload(conn: PgConn, settings: Settings) -> OverviewResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                MIN(snapshot_ts) AS first_snapshot_ts,
                MAX(snapshot_ts) AS latest_snapshot_ts
            FROM market_snapshots
            """
        )
        snapshot_bounds = cur.fetchone()
    first_snapshot_ts = snapshot_bounds["first_snapshot_ts"] if snapshot_bounds else None
    latest_snapshot_ts = snapshot_bounds["latest_snapshot_ts"] if snapshot_bounds else None
    latest_watchlist_snapshot_ts = _latest_watchlist_snapshot_ts(conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM markets")
        markets_discovered = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            {_scanner_scope_cte()}
            SELECT COUNT(*) AS n FROM scanner_scope
            """,
            {"market_limit": settings.market_limit},
        )
        active_scanner_scope = int(cur.fetchone()["n"])

    watchlist_candidates = 0
    if latest_watchlist_snapshot_ts:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM watchlist_candidates
                WHERE snapshot_ts = %s
                """,
                (latest_watchlist_snapshot_ts,),
            )
            watchlist_candidates = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM alerts")
        alerts_count = int(cur.fetchone()["n"])

    backtestable = {}
    for hours in DEFAULT_BACKTEST_HORIZONS:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM alerts a
                LEFT JOIN markets m ON m.condition_id = a.condition_id
                WHERE a.alert_ts <= (NOW() AT TIME ZONE 'UTC' - interval '1 hour' * %s)::text
                  AND (
                    m.yes_token_id IS NOT NULL
                    OR EXISTS (
                        SELECT 1
                        FROM market_snapshots ms
                        WHERE ms.condition_id = a.condition_id
                          AND ms.snapshot_ts >= a.alert_ts
                    )
                  )
                """,
                (hours,),
            )
            row = cur.fetchone()
            backtestable[hours] = int(row["n"]) if row else 0

    return OverviewResponse(
        generated_at=utc_now_iso(),
        db_age=_format_age(first_snapshot_ts),
        first_snapshot_ts=first_snapshot_ts,
        latest_snapshot_ts=latest_snapshot_ts,
        markets_discovered=markets_discovered,
        active_scanner_scope=active_scanner_scope,
        markets_with_enough_6h_history=_history_ready_count(conn, market_limit=settings.market_limit, hours=6),
        markets_with_enough_24h_history=_history_ready_count(conn, market_limit=settings.market_limit, hours=24),
        markets_with_enough_72h_history=_history_ready_count(conn, market_limit=settings.market_limit, hours=72),
        watchlist_candidates=watchlist_candidates,
        alerts_count=alerts_count,
        backtestable_alerts_6h=backtestable[6],
        backtestable_alerts_24h=backtestable[24],
        backtestable_alerts_72h=backtestable[72],
        latest_watchlist_snapshot_ts=latest_watchlist_snapshot_ts,
        latest_backtest_ts=_file_updated_at(settings.backtest_csv_path),
    )


def get_overview(conn: PgConn, settings: Settings) -> OverviewResponse:
    return _overview_payload(conn, settings)


def list_markets(
    conn: PgConn,
    settings: Settings,
    *,
    search: str | None = None,
    status: str = "open",
    history: str | None = None,
    watchlist_only: bool = False,
    sort: str = "watchlist_desc",
    limit: int = 50,
    offset: int = 0,
) -> MarketsResponse:
    filters: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if search:
        filters.append("(LOWER(base.title) LIKE %(search)s OR LOWER(COALESCE(base.category, '')) LIKE %(search)s)")
        params["search"] = f"%{search.lower()}%"
    if status == "open":
        filters.append("base.active = 1 AND base.closed = 0")
    elif status == "closed":
        filters.append("base.closed = 1")
    elif status == "archived":
        filters.append("base.archived = 1")
    if watchlist_only:
        filters.append("base.watchlist_flag = 1")
    if history in {"6h", "24h", "72h"}:
        filters.append(f"base.history_ready_{history[:-1]} = 1")

    order_by = {
        "title_asc": "base.title ASC",
        "yes_price_desc": "(base.current_yes_price IS NULL) ASC, base.current_yes_price DESC",
        "yes_price_asc": "(base.current_yes_price IS NULL) DESC, base.current_yes_price ASC",
        "end_date_asc": "(base.end_date IS NULL) DESC, base.end_date ASC",
        "end_date_desc": "(base.end_date IS NULL) ASC, base.end_date DESC",
        "top5_desc": "(base.yes_top5_seen_share IS NULL) ASC, base.yes_top5_seen_share DESC",
        "holders_desc": "(base.observed_holder_wallets IS NULL) ASC, base.observed_holder_wallets DESC",
        "latest_snapshot_desc": "(base.latest_snapshot_ts IS NULL) ASC, base.latest_snapshot_ts DESC",
        "watchlist_desc": "base.watchlist_flag DESC, base.trade_enriched DESC, (base.latest_snapshot_ts IS NULL) ASC, base.latest_snapshot_ts DESC",
    }.get(sort, "base.watchlist_flag DESC, base.trade_enriched DESC, (base.latest_snapshot_ts IS NULL) ASC, base.latest_snapshot_ts DESC")

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

    base_sql = f"""
    WITH scoped_markets AS (
        SELECT *
        FROM markets
    ),
    latest_snapshot AS (
        SELECT ms.*
        FROM market_snapshots ms
        JOIN (
            SELECT condition_id, MAX(snapshot_ts) AS snapshot_ts
            FROM market_snapshots
            GROUP BY condition_id
        ) latest
          ON latest.condition_id = ms.condition_id
         AND latest.snapshot_ts = ms.snapshot_ts
    ),
    latest_watchlist_cycle AS (
        SELECT MAX(snapshot_ts) AS snapshot_ts FROM watchlist_candidates
    ),
    current_watchlist AS (
        SELECT wc.*
        FROM watchlist_candidates wc
        JOIN latest_watchlist_cycle lw ON lw.snapshot_ts = wc.snapshot_ts
    ),
    latest_alerts AS (
        SELECT a.condition_id, MAX(a.alert_ts) AS latest_alert_ts
        FROM alerts a
        GROUP BY a.condition_id
    ),
    latest_alert_meta AS (
        SELECT a.condition_id, a.alert_ts, a.severity
        FROM alerts a
        JOIN latest_alerts la
          ON la.condition_id = a.condition_id
         AND la.latest_alert_ts = a.alert_ts
    ),
    base AS (
        SELECT
            s.condition_id,
            s.title,
            s.market_id,
            s.event_slug,
            s.slug AS market_slug,
            COALESCE(
                s.market_url,
                CASE
                    WHEN COALESCE(s.event_slug, s.slug) IS NOT NULL
                    THEN 'https://polymarket.com/event/' || COALESCE(s.event_slug, s.slug)
                END
            ) AS market_url,
            s.category,
            s.active,
            s.closed,
            s.archived,
            s.accepting_orders,
            s.end_date,
            ls.snapshot_ts AS latest_snapshot_ts,
            ls.yes_price AS current_yes_price,
            ls.yes_top5_seen_share,
            ls.observed_holder_wallets,
            EXISTS (
                SELECT 1
                FROM market_snapshots ms6
                WHERE ms6.condition_id = s.condition_id
                  AND ls.snapshot_ts IS NOT NULL
                  AND ms6.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '6 hours')::text
            ) AS history_ready_6,
            EXISTS (
                SELECT 1
                FROM market_snapshots ms24
                WHERE ms24.condition_id = s.condition_id
                  AND ls.snapshot_ts IS NOT NULL
                  AND ms24.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '24 hours')::text
            ) AS history_ready_24,
            EXISTS (
                SELECT 1
                FROM market_snapshots ms72
                WHERE ms72.condition_id = s.condition_id
                  AND ls.snapshot_ts IS NOT NULL
                  AND ms72.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '72 hours')::text
            ) AS history_ready_72,
            CASE WHEN cw.condition_id IS NULL THEN 0 ELSE 1 END AS watchlist_flag,
            COALESCE(cw.warmup_only, 0) AS warmup_only,
            CASE
                WHEN EXISTS (SELECT 1 FROM trades t WHERE t.condition_id = s.condition_id)
                THEN 1 ELSE COALESCE(cw.trade_enriched, 0)
            END AS trade_enriched,
            lam.alert_ts AS latest_alert_ts,
            lam.severity AS latest_alert_severity
        FROM scoped_markets s
        LEFT JOIN latest_snapshot ls ON ls.condition_id = s.condition_id
        LEFT JOIN current_watchlist cw ON cw.condition_id = s.condition_id
        LEFT JOIN latest_alert_meta lam ON lam.condition_id = s.condition_id
    )
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            {base_sql}
            SELECT COUNT(*) AS n
            FROM base
            {where_sql}
            """,
            params,
        )
        total = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            {base_sql}
            SELECT *
            FROM base
            {where_sql}
            ORDER BY {order_by}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = cur.fetchall()

    items = [
        MarketSummary(
            condition_id=row["condition_id"],
            title=row["title"],
            market_id=row["market_id"],
            event_slug=row["event_slug"],
            market_slug=row["market_slug"],
            market_url=row["market_url"],
            category=row["category"],
            active=bool(row["active"]),
            closed=bool(row["closed"]),
            accepting_orders=bool(row["accepting_orders"]) if row["accepting_orders"] is not None else None,
            end_date=row["end_date"],
            latest_snapshot_ts=row["latest_snapshot_ts"],
            current_yes_price=row["current_yes_price"],
            yes_top5_seen_share=row["yes_top5_seen_share"],
            observed_holder_wallets=row["observed_holder_wallets"],
            history_ready_6h=bool(row["history_ready_6"]),
            history_ready_24h=bool(row["history_ready_24"]),
            history_ready_72h=bool(row["history_ready_72"]),
            watchlist_flag=bool(row["watchlist_flag"]),
            warmup_only=bool(row["warmup_only"]),
            trade_enriched=bool(row["trade_enriched"]),
            latest_alert_ts=row["latest_alert_ts"],
            latest_alert_severity=row["latest_alert_severity"],
        )
        for row in rows
    ]
    return MarketsResponse(total=total, items=items)


def get_watchlist(
    conn: PgConn,
    *,
    warmup_only: bool | None = None,
    limit: int = 100,
) -> WatchlistResponse:
    snapshot_ts = _latest_watchlist_snapshot_ts(conn)
    if not snapshot_ts:
        return WatchlistResponse(snapshot_ts=None, total=0, items=[])

    filters = ["wc.snapshot_ts = %(snapshot_ts)s"]
    params: Dict[str, Any] = {"snapshot_ts": snapshot_ts, "limit": limit}
    if warmup_only is True:
        filters.append("wc.warmup_only = 1")
    elif warmup_only is False:
        filters.append("wc.warmup_only = 0")

    where_sql = " AND ".join(filters)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT COUNT(*) AS n FROM watchlist_candidates wc WHERE {where_sql}",
            params,
        )
        total = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT wc.*
            FROM watchlist_candidates wc
            WHERE {where_sql}
            ORDER BY wc.trade_enriched DESC, wc.history_ready_6h DESC, wc.price_anomaly_hit DESC, wc.market_title ASC
            LIMIT %(limit)s
            """,
            params,
        )
        rows = cur.fetchall()

    items = [
        WatchlistCandidateResponse(
            snapshot_ts=row["snapshot_ts"],
            condition_id=row["condition_id"],
            market_title=row["market_title"],
            market_url=build_market_url(None, None),
            current_yes_price=row["current_yes_price"],
            price_delta_6h=row["price_delta_6h"],
            yes_top5_seen_share=row["yes_top5_seen_share"],
            price_anomaly_hit=bool(row["price_anomaly_hit"]),
            holder_concentration_hit=bool(row["holder_concentration_hit"]),
            wallet_quality_hit=bool(row["wallet_quality_hit"]),
            warmup_only=bool(row["warmup_only"]),
            history_ready_6h=bool(row["history_ready_6h"]),
            trade_enriched=bool(row["trade_enriched"]),
            reason_summary=row["reason_summary"],
            component_flags=_json_loads(row["component_flags_json"], {}),
        )
        for row in rows
    ]

    if items:
        placeholders = ",".join("%s" for _ in items)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT condition_id, event_slug, slug
                FROM markets
                WHERE condition_id IN ({placeholders})
                """,
                tuple(item.condition_id for item in items),
            )
            market_rows = cur.fetchall()
        urls = {
            row["condition_id"]: build_market_url(row["event_slug"], row["slug"])
            for row in market_rows
        }
        items = [item.model_copy(update={"market_url": urls.get(item.condition_id)}) for item in items]

    return WatchlistResponse(snapshot_ts=snapshot_ts, total=total, items=items)


def list_alerts(
    conn: PgConn,
    *,
    severity: str | None = None,
    confidence: str | None = None,
    alert_type: str | None = None,
    condition_id: str | None = None,
    hours: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AlertsResponse:
    filters: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if severity:
        filters.append("severity = %(severity)s")
        params["severity"] = severity
    if confidence:
        filters.append("confidence = %(confidence)s")
        params["confidence"] = confidence
    if alert_type:
        filters.append("alert_type = %(alert_type)s")
        params["alert_type"] = alert_type
    if condition_id:
        filters.append("condition_id = %(condition_id)s")
        params["condition_id"] = condition_id
    if hours is not None:
        filters.append("alert_ts >= (NOW() AT TIME ZONE 'UTC' - interval '1 hour' * %(hours)s)::text")
        params["hours"] = hours
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM alerts {where_sql}", params)
        total = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT *
            FROM alerts
            {where_sql}
            ORDER BY alert_ts DESC, id DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = cur.fetchall()

    return AlertsResponse(
        total=total,
        items=[
            AlertResponse(
                id=row["id"],
                alert_ts=row["alert_ts"],
                condition_id=row["condition_id"],
                market_title=row["market_title"],
                market_url=row["market_url"],
                alert_type=row["alert_type"],
                score=row["score"],
                score_total=row["score_total"],
                score_price_anomaly=row["score_price_anomaly"],
                score_holder_concentration=row["score_holder_concentration"],
                score_wallet_quality=row["score_wallet_quality"],
                score_trade_flow=row["score_trade_flow"],
                current_yes_price=row["current_yes_price"],
                price_delta_6h=row["price_delta_6h"],
                price_delta_24h=row["price_delta_24h"],
                price_delta_72h=row["price_delta_72h"],
                severity=row["severity"],
                confidence=row["confidence"],
                action_label=row["action_label"],
                reason_summary=row["reason_summary"],
                summary=row["summary"],
                reasons=_normalize_alert_reasons(row["reasons_json"]),
                sent=bool(row["sent"]),
            )
            for row in rows
        ],
    )


def _build_recommendation_response(rows: List[Dict[str, Any]]) -> RecommendationsResponse:
    items: List[RecommendationItemResponse] = []
    for row in rows:
        current_yes_price = row["latest_yes_price"] if row["latest_yes_price"] is not None else row["entry_yes_price"]
        current_return = _pct_change(row["entry_yes_price"], current_yes_price)
        final_yes_price = resolved_yes_price(row["raw_json"], row["latest_yes_price"]) if row["closed"] else None
        outcome_return, verdict = outcome_verdict(row["entry_yes_price"], final_yes_price)
        status = "settled" if row["closed"] else row["status"]

        items.append(
            RecommendationItemResponse(
                condition_id=row["condition_id"],
                market_title=row["market_title"],
                market_url=row["market_url"],
                source=row["source"],
                side=row["side"],
                recommendation=row["recommendation"],
                status=status,
                conviction_score=row["conviction_score"],
                severity=row["severity"],
                confidence=row["confidence"],
                reason_summary=row["reason_summary"],
                entry_ts=row["entry_ts"],
                entry_yes_price=row["entry_yes_price"],
                latest_snapshot_ts=row["latest_snapshot_ts"],
                current_yes_price=current_yes_price,
                current_return=current_return,
                final_yes_price=final_yes_price,
                outcome_return=outcome_return,
                outcome_verdict=verdict,
                closed=bool(row["closed"]),
                closed_time=row["closed_time"],
                history_ready_6h=bool(row["history_ready_6h"]),
                warmup_only=bool(row["warmup_only"]),
                trade_enriched=bool(row["trade_enriched"]),
            )
        )

    status_order = {"actionable": 0, "monitoring": 1, "settled": 2}
    items.sort(
        key=lambda item: (
            status_order.get(item.status, 99),
            -item.conviction_score,
            item.entry_ts,
        )
    )
    return RecommendationsResponse(
        total=len(items),
        actionable=sum(1 for item in items if item.status == "actionable"),
        monitoring=sum(1 for item in items if item.status == "monitoring"),
        settled=sum(1 for item in items if item.status == "settled"),
        items=items,
    )


def _list_recommendations_derived(conn: PgConn, *, limit: int = 100) -> RecommendationsResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH latest_snapshot AS (
                SELECT ms.*
                FROM market_snapshots ms
                JOIN (
                    SELECT condition_id, MAX(snapshot_ts) AS snapshot_ts
                    FROM market_snapshots
                    GROUP BY condition_id
                ) latest
                  ON latest.condition_id = ms.condition_id
                 AND latest.snapshot_ts = ms.snapshot_ts
            ),
            latest_watchlist_cycle AS (
                SELECT MAX(snapshot_ts) AS snapshot_ts
                FROM watchlist_candidates
            ),
            current_watchlist AS (
                SELECT wc.*
                FROM watchlist_candidates wc
                JOIN latest_watchlist_cycle lw
                  ON lw.snapshot_ts = wc.snapshot_ts
            ),
            latest_alert_key AS (
                SELECT condition_id, MAX(alert_ts) AS alert_ts
                FROM alerts
                GROUP BY condition_id
            ),
            latest_alert AS (
                SELECT a.*
                FROM alerts a
                JOIN latest_alert_key lk
                  ON lk.condition_id = a.condition_id
                 AND lk.alert_ts = a.alert_ts
            ),
            scoped AS (
                SELECT
                    m.condition_id,
                    m.title AS market_title,
                    COALESCE(
                        m.market_url,
                        CASE
                            WHEN COALESCE(m.event_slug, m.slug) IS NOT NULL
                            THEN 'https://polymarket.com/event/' || COALESCE(m.event_slug, m.slug)
                        END
                    ) AS market_url,
                    m.closed,
                    m.closed_time,
                    m.raw_json,
                    ls.snapshot_ts AS latest_snapshot_ts,
                    ls.yes_price AS latest_yes_price,
                    la.alert_ts,
                    la.current_yes_price AS alert_entry_yes_price,
                    la.score_total,
                    la.severity,
                    la.confidence,
                    la.reason_summary AS alert_reason_summary,
                    cw.snapshot_ts AS watchlist_snapshot_ts,
                    cw.current_yes_price AS watchlist_entry_yes_price,
                    cw.reason_summary AS watchlist_reason_summary,
                    COALESCE(cw.price_anomaly_hit, 0) AS price_anomaly_hit,
                    COALESCE(cw.holder_concentration_hit, 0) AS holder_concentration_hit,
                    COALESCE(cw.wallet_quality_hit, 0) AS wallet_quality_hit,
                    COALESCE(cw.history_ready_6h, 0) AS history_ready_6h,
                    COALESCE(cw.warmup_only, 0) AS warmup_only,
                    COALESCE(
                        CASE
                            WHEN EXISTS (SELECT 1 FROM trades t WHERE t.condition_id = m.condition_id) THEN 1
                            ELSE cw.trade_enriched
                        END,
                        0
                    ) AS trade_enriched
                FROM markets m
                LEFT JOIN latest_snapshot ls ON ls.condition_id = m.condition_id
                LEFT JOIN latest_alert la ON la.condition_id = m.condition_id
                LEFT JOIN current_watchlist cw ON cw.condition_id = m.condition_id
                WHERE la.condition_id IS NOT NULL OR cw.condition_id IS NOT NULL
            )
            SELECT *
            FROM scoped
            ORDER BY COALESCE(alert_ts, watchlist_snapshot_ts) DESC, market_title ASC
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
        rows = cur.fetchall()

    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        source = "alert" if row["alert_ts"] else "watchlist"
        entry_ts = row["alert_ts"] or row["watchlist_snapshot_ts"]
        entry_yes_price = row["alert_entry_yes_price"] if row["alert_ts"] else row["watchlist_entry_yes_price"]
        recommendation, status, conviction_score = recommendation_meta(row)
        normalized_rows.append(
            {
                "condition_id": row["condition_id"],
                "market_title": row["market_title"],
                "market_url": row["market_url"],
                "source": source,
                "side": "Yes",
                "recommendation": recommendation,
                "status": status,
                "conviction_score": conviction_score,
                "severity": row["severity"],
                "confidence": row["confidence"],
                "reason_summary": row["alert_reason_summary"] or row["watchlist_reason_summary"],
                "entry_ts": entry_ts,
                "entry_yes_price": entry_yes_price,
                "latest_snapshot_ts": row["latest_snapshot_ts"],
                "latest_yes_price": row["latest_yes_price"],
                "closed": row["closed"],
                "closed_time": row["closed_time"],
                "history_ready_6h": row["history_ready_6h"],
                "warmup_only": row["warmup_only"],
                "trade_enriched": row["trade_enriched"],
                "raw_json": row["raw_json"],
            }
        )

    return _build_recommendation_response(normalized_rows)


def list_recommendations(conn: PgConn, *, limit: int = 100) -> RecommendationsResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM recommendations")
        recommendation_count = int(cur.fetchone()["n"] or 0)
    if recommendation_count == 0:
        return _list_recommendations_derived(conn, limit=limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    r.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.condition_id
                        ORDER BY r.entry_ts DESC, CASE WHEN r.source = 'alert' THEN 0 ELSE 1 END, r.id DESC
                    ) AS rn
                FROM recommendations r
            ),
            latest_recommendation AS (
                SELECT *
                FROM ranked
                WHERE rn = 1
            ),
            latest_snapshot AS (
                SELECT ms.*
                FROM market_snapshots ms
                JOIN (
                    SELECT condition_id, MAX(snapshot_ts) AS snapshot_ts
                    FROM market_snapshots
                    GROUP BY condition_id
                ) latest
                  ON latest.condition_id = ms.condition_id
                 AND latest.snapshot_ts = ms.snapshot_ts
            )
            SELECT
                lr.entry_ts,
                lr.condition_id,
                lr.source,
                lr.market_title,
                lr.market_url,
                lr.side,
                lr.recommendation,
                lr.status,
                lr.conviction_score,
                lr.severity,
                lr.confidence,
                lr.reason_summary,
                lr.entry_yes_price,
                lr.history_ready_6h,
                lr.warmup_only,
                lr.trade_enriched,
                m.closed,
                m.closed_time,
                m.raw_json,
                ls.snapshot_ts AS latest_snapshot_ts,
                ls.yes_price AS latest_yes_price
            FROM latest_recommendation lr
            JOIN markets m ON m.condition_id = lr.condition_id
            LEFT JOIN latest_snapshot ls ON ls.condition_id = lr.condition_id
            ORDER BY lr.entry_ts DESC, lr.market_title ASC
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
        rows = [dict(row) for row in cur.fetchall()]

    return _build_recommendation_response(rows)


def get_market_detail(conn: PgConn, condition_id: str) -> MarketDetailResponse | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH latest_snapshot AS (
                SELECT *
                FROM market_snapshots
                WHERE condition_id = %(condition_id)s
                ORDER BY snapshot_ts DESC
                LIMIT 1
            ),
            latest_watchlist_cycle AS (
                SELECT MAX(snapshot_ts) AS snapshot_ts FROM watchlist_candidates
            ),
            current_watchlist AS (
                SELECT *
                FROM watchlist_candidates
                WHERE condition_id = %(condition_id)s
                  AND snapshot_ts = (SELECT snapshot_ts FROM latest_watchlist_cycle)
            ),
            latest_alert AS (
                SELECT alert_ts, severity
                FROM alerts
                WHERE condition_id = %(condition_id)s
                ORDER BY alert_ts DESC, id DESC
                LIMIT 1
            )
            SELECT
                m.*,
                ls.yes_price AS current_yes_price,
                ls.no_price AS current_no_price,
                ls.yes_top5_seen_share,
                ls.no_top5_seen_share,
                ls.observed_holder_wallets,
                ls.snapshot_ts AS latest_snapshot_ts,
                EXISTS (
                    SELECT 1 FROM market_snapshots ms
                    WHERE ms.condition_id = m.condition_id
                      AND ls.snapshot_ts IS NOT NULL
                      AND ms.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '6 hours')::text
                ) AS history_ready_6,
                EXISTS (
                    SELECT 1 FROM market_snapshots ms
                    WHERE ms.condition_id = m.condition_id
                      AND ls.snapshot_ts IS NOT NULL
                      AND ms.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '24 hours')::text
                ) AS history_ready_24,
                EXISTS (
                    SELECT 1 FROM market_snapshots ms
                    WHERE ms.condition_id = m.condition_id
                      AND ls.snapshot_ts IS NOT NULL
                      AND ms.snapshot_ts <= (ls.snapshot_ts::timestamp - interval '72 hours')::text
                ) AS history_ready_72,
                CASE WHEN cw.condition_id IS NULL THEN 0 ELSE 1 END AS watchlist_flag,
                COALESCE(cw.warmup_only, 0) AS warmup_only,
                CASE
                    WHEN EXISTS (SELECT 1 FROM trades t WHERE t.condition_id = m.condition_id)
                    THEN 1 ELSE COALESCE(cw.trade_enriched, 0)
                END AS trade_enriched,
                cw.reason_summary AS latest_watchlist_reason_summary,
                (SELECT COUNT(*) FROM alerts a WHERE a.condition_id = m.condition_id) AS recent_alert_count,
                la.alert_ts AS latest_alert_ts,
                la.severity AS latest_alert_severity
            FROM markets m
            LEFT JOIN latest_snapshot ls ON 1 = 1
            LEFT JOIN current_watchlist cw ON 1 = 1
            LEFT JOIN latest_alert la ON 1 = 1
            WHERE m.condition_id = %(condition_id)s
            """,
            {"condition_id": condition_id},
        )
        row = cur.fetchone()

    if not row:
        return None
    return MarketDetailResponse(
        condition_id=row["condition_id"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        market_id=row["market_id"],
        question_id=row["question_id"],
        event_slug=row["event_slug"],
        market_slug=row["slug"],
        market_url=row["market_url"] or build_market_url(row["event_slug"], row["slug"]),
        active=bool(row["active"]),
        closed=bool(row["closed"]),
        archived=bool(row["archived"]),
        accepting_orders=bool(row["accepting_orders"]) if row["accepting_orders"] is not None else None,
        end_date=row["end_date"],
        closed_time=row["closed_time"],
        yes_token_id=row["yes_token_id"],
        no_token_id=row["no_token_id"],
        image_url=row["image_url"],
        reward_asset_address=row["reward_asset_address"],
        discovered_at=row["discovered_at"],
        last_seen_at=row["last_seen_at"],
        current_yes_price=row["current_yes_price"],
        current_no_price=row["current_no_price"],
        yes_top5_seen_share=row["yes_top5_seen_share"],
        no_top5_seen_share=row["no_top5_seen_share"],
        observed_holder_wallets=row["observed_holder_wallets"],
        history_ready_6h=bool(row["history_ready_6"]),
        history_ready_24h=bool(row["history_ready_24"]),
        history_ready_72h=bool(row["history_ready_72"]),
        watchlist_flag=bool(row["watchlist_flag"]),
        warmup_only=bool(row["warmup_only"]),
        trade_enriched=bool(row["trade_enriched"]),
        recent_alert_count=int(row["recent_alert_count"] or 0),
        latest_alert_ts=row["latest_alert_ts"],
        latest_alert_severity=row["latest_alert_severity"],
        latest_watchlist_reason_summary=row["latest_watchlist_reason_summary"],
    )


def get_market_timeseries(conn: PgConn, condition_id: str, hours: int) -> TimeSeriesResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT MAX(snapshot_ts) AS snapshot_ts
            FROM market_snapshots
            WHERE condition_id = %s
            """,
            (condition_id,),
        )
        latest = cur.fetchone()
    latest_snapshot_ts = latest["snapshot_ts"] if latest else None
    if not latest_snapshot_ts:
        return TimeSeriesResponse(condition_id=condition_id, hours=hours, items=[])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT snapshot_ts, yes_price, no_price, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets
            FROM market_snapshots
            WHERE condition_id = %s
              AND snapshot_ts >= (%s::timestamp - interval '1 hour' * %s)::text
            ORDER BY snapshot_ts ASC
            """,
            (condition_id, latest_snapshot_ts, hours),
        )
        rows = cur.fetchall()

    return TimeSeriesResponse(
        condition_id=condition_id,
        hours=hours,
        items=[
            TimeSeriesPoint(
                snapshot_ts=row["snapshot_ts"],
                yes_price=row["yes_price"],
                no_price=row["no_price"],
                yes_top5_seen_share=row["yes_top5_seen_share"],
                no_top5_seen_share=row["no_top5_seen_share"],
                observed_holder_wallets=row["observed_holder_wallets"],
            )
            for row in rows
        ],
    )


def get_market_holders(conn: PgConn, condition_id: str, snapshot: str = "latest") -> HoldersResponse:
    snapshot_ts = snapshot
    if snapshot == "latest":
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT MAX(snapshot_ts) AS snapshot_ts
                FROM holder_snapshots
                WHERE condition_id = %s
                """,
                (condition_id,),
            )
            row = cur.fetchone()
            snapshot_ts = row["snapshot_ts"] if row else None

    if not snapshot_ts:
        return HoldersResponse(condition_id=condition_id, snapshot_ts=None, items=[])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                hs.snapshot_ts,
                hs.token_id,
                hs.wallet_address,
                hs.amount,
                hs.outcome_index,
                hs.rank,
                ws.politics_score,
                ws.overall_score,
                ws.politics_pnl_rank,
                ws.overall_pnl_rank
            FROM holder_snapshots hs
            LEFT JOIN wallet_scores ws ON ws.wallet_address = hs.wallet_address
            WHERE hs.condition_id = %s
              AND hs.snapshot_ts = %s
            ORDER BY hs.rank ASC, hs.amount DESC
            """,
            (condition_id, snapshot_ts),
        )
        rows = cur.fetchall()

    return HoldersResponse(
        condition_id=condition_id,
        snapshot_ts=snapshot_ts,
        items=[
            HolderResponse(
                snapshot_ts=row["snapshot_ts"],
                token_id=row["token_id"],
                wallet_address=row["wallet_address"],
                amount=row["amount"],
                outcome_index=row["outcome_index"],
                rank=row["rank"],
                politics_score=row["politics_score"],
                overall_score=row["overall_score"],
                politics_pnl_rank=row["politics_pnl_rank"],
                overall_pnl_rank=row["overall_pnl_rank"],
            )
            for row in rows
        ],
    )


def get_market_trades(conn: PgConn, condition_id: str, limit: int = 50) -> TradesResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT trade_key, trade_ts, wallet_address, side, outcome, price, size, notional, tx_hash, title
            FROM trades
            WHERE condition_id = %s
            ORDER BY trade_ts DESC, trade_key DESC
            LIMIT %s
            """,
            (condition_id, limit),
        )
        rows = cur.fetchall()

    return TradesResponse(
        condition_id=condition_id,
        total=len(rows),
        items=[
            TradeResponse(
                trade_key=row["trade_key"],
                trade_ts=row["trade_ts"],
                wallet_address=row["wallet_address"],
                side=row["side"],
                outcome=row["outcome"],
                price=row["price"],
                size=row["size"],
                notional=row["notional"],
                tx_hash=row["tx_hash"],
                title=row["title"],
            )
            for row in rows
        ],
    )


def get_market_trade_aftermath(
    conn: PgConn,
    condition_id: str,
    *,
    limit: int = 10,
    min_notional: float | None = None,
    side: str | None = "buy",
    outcome: str | None = None,
) -> TradeAftermathResponse:
    filters = ["t.condition_id = %(condition_id)s"]
    params: Dict[str, Any] = {"condition_id": condition_id, "limit": limit}

    normalized_side = None if not side or side.lower() == "all" else side.lower()
    normalized_outcome = None if not outcome or outcome.lower() == "all" else outcome.title()

    if normalized_side:
        filters.append("LOWER(COALESCE(t.side, '')) = %(side)s")
        params["side"] = normalized_side
    if normalized_outcome:
        filters.append("COALESCE(t.outcome, '') = %(outcome)s")
        params["outcome"] = normalized_outcome
    if min_notional is not None:
        filters.append("t.notional >= %(min_notional)s")
        params["min_notional"] = min_notional

    where_sql = " AND ".join(filters)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT COUNT(*) AS n FROM trades t WHERE {where_sql}",
            params,
        )
        total = int(cur.fetchone()["n"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                t.trade_key,
                t.trade_ts,
                t.wallet_address,
                t.side,
                t.outcome,
                t.price,
                t.size,
                t.notional,
                t.tx_hash,
                t.title,
                ws.politics_score,
                ws.overall_score,
                ws.politics_pnl_rank,
                ws.overall_pnl_rank
            FROM trades t
            LEFT JOIN wallet_scores ws ON ws.wallet_address = t.wallet_address
            WHERE {where_sql}
            ORDER BY (t.notional IS NULL) ASC, t.notional DESC, t.trade_ts DESC, t.trade_key DESC
            LIMIT %(limit)s
            """,
            params,
        )
        trade_rows = cur.fetchall()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT snapshot_ts, yes_price, no_price, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets
            FROM market_snapshots
            WHERE condition_id = %s
            ORDER BY snapshot_ts ASC
            """,
            (condition_id,),
        )
        raw_snapshot_rows = cur.fetchall()

    snapshot_rows: List[Dict[str, Any]] = []
    snapshot_times: List[datetime] = []
    for row in raw_snapshot_rows:
        parsed_ts = _parse_db_ts(row["snapshot_ts"])
        if parsed_ts is None:
            continue
        snapshot_rows.append(row)
        snapshot_times.append(parsed_ts)

    latest_snapshot = snapshot_rows[-1] if snapshot_rows else None
    latest_snapshot_dt = snapshot_times[-1] if snapshot_times else None

    def outcome_price(snapshot: Dict[str, Any] | None, trade_outcome: str | None) -> float | None:
        if snapshot is None or not trade_outcome:
            return None
        lowered = trade_outcome.lower()
        if lowered == "yes":
            return snapshot["yes_price"]
        if lowered == "no":
            return snapshot["no_price"]
        return None

    items: List[TradeAftermathTradeResponse] = []
    for row in trade_rows:
        trade_dt = _parse_db_ts(row["trade_ts"])

        entry_snapshot = None
        entry_snapshot_dt = None
        surrounding_points: List[TradeAftermathPoint] = []
        horizons: List[TradeAftermathHorizon] = []

        if trade_dt is not None and snapshot_times:
            entry_idx = bisect_right(snapshot_times, trade_dt) - 1
            if entry_idx >= 0:
                entry_snapshot = snapshot_rows[entry_idx]
                entry_snapshot_dt = snapshot_times[entry_idx]

            start_idx = bisect_left(snapshot_times, trade_dt - timedelta(hours=24))
            end_idx = bisect_right(snapshot_times, trade_dt + timedelta(hours=72))
            for idx in range(start_idx, end_idx):
                snapshot = snapshot_rows[idx]
                relative_hours = (snapshot_times[idx] - trade_dt).total_seconds() / 3600
                surrounding_points.append(
                    TradeAftermathPoint(
                        snapshot_ts=snapshot["snapshot_ts"],
                        yes_price=snapshot["yes_price"],
                        no_price=snapshot["no_price"],
                        yes_top5_seen_share=snapshot["yes_top5_seen_share"],
                        no_top5_seen_share=snapshot["no_top5_seen_share"],
                        observed_holder_wallets=snapshot["observed_holder_wallets"],
                        relative_hours=_round_hours(relative_hours),
                    )
                )
            for horizon_hours in (6, 24, 72):
                horizon_dt = trade_dt + timedelta(hours=horizon_hours)
                horizon_idx = bisect_left(snapshot_times, horizon_dt)
                horizon_snapshot = snapshot_rows[horizon_idx] if horizon_idx < len(snapshot_rows) else None
                observed_hours_after_trade = None
                if horizon_snapshot is not None:
                    observed_hours_after_trade = (snapshot_times[horizon_idx] - trade_dt).total_seconds() / 3600
                horizons.append(
                    TradeAftermathHorizon(
                        target_hours=horizon_hours,
                        snapshot_ts=horizon_snapshot["snapshot_ts"] if horizon_snapshot is not None else None,
                        observed_hours_after_trade=_round_hours(observed_hours_after_trade),
                        yes_price=horizon_snapshot["yes_price"] if horizon_snapshot is not None else None,
                        no_price=horizon_snapshot["no_price"] if horizon_snapshot is not None else None,
                        yes_return=_pct_change(
                            entry_snapshot["yes_price"] if entry_snapshot is not None else None,
                            horizon_snapshot["yes_price"] if horizon_snapshot is not None else None,
                        ),
                        no_return=_pct_change(
                            entry_snapshot["no_price"] if entry_snapshot is not None else None,
                            horizon_snapshot["no_price"] if horizon_snapshot is not None else None,
                        ),
                        outcome_price=outcome_price(horizon_snapshot, row["outcome"]),
                        outcome_return=_pct_change(row["price"], outcome_price(horizon_snapshot, row["outcome"])),
                    )
                )

        entry_yes_price = entry_snapshot["yes_price"] if entry_snapshot is not None else None
        entry_no_price = entry_snapshot["no_price"] if entry_snapshot is not None else None
        current_outcome_price = outcome_price(latest_snapshot, row["outcome"])
        has_post_trade_snapshot = bool(trade_dt is not None and latest_snapshot_dt is not None and latest_snapshot_dt >= trade_dt)

        entry_snapshot_lag_minutes = None
        if trade_dt is not None and entry_snapshot_dt is not None:
            entry_snapshot_lag_minutes = (trade_dt - entry_snapshot_dt).total_seconds() / 60

        items.append(
            TradeAftermathTradeResponse(
                trade_key=row["trade_key"],
                trade_ts=row["trade_ts"],
                wallet_address=row["wallet_address"],
                side=row["side"],
                outcome=row["outcome"],
                price=row["price"],
                size=row["size"],
                notional=row["notional"],
                tx_hash=row["tx_hash"],
                title=row["title"],
                politics_score=row["politics_score"],
                overall_score=row["overall_score"],
                politics_pnl_rank=row["politics_pnl_rank"],
                overall_pnl_rank=row["overall_pnl_rank"],
                entry_snapshot_ts=entry_snapshot["snapshot_ts"] if entry_snapshot is not None else None,
                entry_snapshot_lag_minutes=_round_minutes(entry_snapshot_lag_minutes),
                entry_yes_price=entry_yes_price,
                entry_no_price=entry_no_price,
                current_snapshot_ts=latest_snapshot["snapshot_ts"] if latest_snapshot is not None else None,
                current_yes_price=latest_snapshot["yes_price"] if latest_snapshot is not None else None,
                current_no_price=latest_snapshot["no_price"] if latest_snapshot is not None else None,
                current_yes_return=(
                    _pct_change(entry_yes_price, latest_snapshot["yes_price"] if latest_snapshot is not None else None)
                    if has_post_trade_snapshot
                    else None
                ),
                current_no_return=(
                    _pct_change(entry_no_price, latest_snapshot["no_price"] if latest_snapshot is not None else None)
                    if has_post_trade_snapshot
                    else None
                ),
                current_outcome_price=current_outcome_price,
                current_outcome_return=_pct_change(row["price"], current_outcome_price) if has_post_trade_snapshot else None,
                horizons=horizons,
                surrounding_points=surrounding_points,
            )
        )

    return TradeAftermathResponse(
        condition_id=condition_id,
        total=total,
        side=normalized_side,
        outcome=normalized_outcome,
        min_notional=min_notional,
        items=items,
    )


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aggregate(values: List[float | None], key: str, count: int) -> AggregateBucket:
    clean = [value for value in values if value is not None]
    avg_return = round(sum(clean) / len(clean), 4) if clean else None
    median_return = round(median(clean), 4) if clean else None
    positive_rate = round(sum(1 for value in clean if value > 0) / len(clean), 4) if clean else None
    return AggregateBucket(key=key, count=count, avg_return=avg_return, median_return=median_return, positive_rate=positive_rate)


def _score_bucket(score_value: float | None) -> str:
    if score_value is None:
        return "unknown"
    if score_value < 5.5:
        return "<5.5"
    if score_value < 8.0:
        return "5.5-7.99"
    return ">=8.0"


def _load_backtest_response(path: Path, *, default_horizons: List[int]) -> BacktestResponse:
    if not path.exists():
        return BacktestResponse(
            csv_path=str(path),
            exists=False,
            updated_at=None,
            total_rows=0,
            horizons=default_horizons,
            score_buckets=[],
            severity_buckets=[],
            confidence_buckets=[],
            alert_type_buckets=[],
            missing_reason_buckets=[],
            rows=[],
        )

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    horizons: List[int] = []
    for field in rows[0].keys() if rows else []:
        if field.startswith("fwd_") and (field.endswith("h_yes_return") or field.endswith("h_outcome_return")):
            value = field.removeprefix("fwd_")
            if value.endswith("h_yes_return"):
                value = value.removesuffix("h_yes_return")
            else:
                value = value.removesuffix("h_outcome_return")
            try:
                horizons.append(int(value))
            except ValueError:
                continue
    horizons = sorted(set(horizons)) or list(default_horizons)

    score_groups: Dict[str, List[float | None]] = {}
    severity_groups: Dict[str, List[float | None]] = {}
    confidence_groups: Dict[str, List[float | None]] = {}
    alert_type_groups: Dict[str, List[float | None]] = {}
    missing_reason_groups: Dict[str, List[float | None]] = {}

    for row in rows:
        score_value = _safe_float(row.get("score_total") or row.get("score"))
        for horizon in horizons:
            return_value = _safe_float(row.get(f"fwd_{horizon}h_yes_return") or row.get(f"fwd_{horizon}h_outcome_return"))
            score_groups.setdefault(f"{horizon}h|{_score_bucket(score_value)}", []).append(return_value)
            severity_groups.setdefault(f"{horizon}h|{row.get('severity') or 'unknown'}", []).append(return_value)
            confidence_groups.setdefault(f"{horizon}h|{row.get('confidence') or 'unknown'}", []).append(return_value)
            alert_type_groups.setdefault(f"{horizon}h|{row.get('alert_type') or 'unknown'}", []).append(return_value)
            missing_reason = row.get(f"missing_reason_{horizon}h") or "none"
            missing_reason_groups.setdefault(f"{horizon}h|{missing_reason}", []).append(return_value)

    def finalize(groups: Dict[str, List[float | None]]) -> List[AggregateBucket]:
        return [
            _aggregate(values, key=key, count=len(values))
            for key, values in sorted(groups.items(), key=lambda item: item[0])
        ]

    return BacktestResponse(
        csv_path=str(path),
        exists=True,
        updated_at=_file_updated_at(path),
        total_rows=len(rows),
        horizons=horizons,
        score_buckets=finalize(score_groups),
        severity_buckets=finalize(severity_groups),
        confidence_buckets=finalize(confidence_groups),
        alert_type_buckets=finalize(alert_type_groups),
        missing_reason_buckets=finalize(missing_reason_groups),
        rows=rows,
    )


def get_backtests(settings: Settings) -> BacktestResponse:
    return _load_backtest_response(settings.backtest_csv_path, default_horizons=list(DEFAULT_BACKTEST_HORIZONS))


def get_latent_backtests(settings: Settings) -> BacktestResponse:
    return _load_backtest_response(settings.latent_backtest_csv_path, default_horizons=list(DEFAULT_LATENT_BACKTEST_HORIZONS))


def get_system(conn: PgConn, settings: Settings) -> SystemResponse:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, job_name, started_at, finished_at, status, rows_written, meta_json, error_text
            FROM job_runs
            ORDER BY started_at DESC, id DESC
            LIMIT 20
            """
        )
        job_rows = cur.fetchall()

    return SystemResponse(
        overview=_overview_payload(conn, settings),
        backtest_csv_path=str(settings.backtest_csv_path),
        backtest_exists=settings.backtest_csv_path.exists(),
        backtest_updated_at=_file_updated_at(settings.backtest_csv_path),
        latent_backtest_csv_path=str(settings.latent_backtest_csv_path),
        latent_backtest_exists=settings.latent_backtest_csv_path.exists(),
        latent_backtest_updated_at=_file_updated_at(settings.latent_backtest_csv_path),
        recent_job_runs=[
            JobRunResponse(
                id=row["id"],
                job_name=row["job_name"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                status=row["status"],
                rows_written=row["rows_written"],
                meta=_json_loads(row["meta_json"], {}),
                error_text=row["error_text"],
            )
            for row in job_rows
        ],
    )
