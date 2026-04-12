from __future__ import annotations

import csv
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import httpx

from .clients.clob import ClobPublicClient
from .config import Settings
from .db import Database

logger = logging.getLogger(__name__)

DEFAULT_BACKTEST_HORIZONS = (6, 24, 72)
DEFAULT_LATENT_BACKTEST_HORIZONS = (24, 72, 120)
_HISTORY_INTERVAL_BY_HOUR = {
    6: "1h",
    24: "1h",
    72: "6h",
}
_INTERVAL_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "1d": 24 * 3600,
}
LOCAL_SNAPSHOT_SOURCE = "local_snapshot"
OFFICIAL_HISTORY_SOURCE = "official_history"
MISSING_SOURCE = "missing"
LATENT_SIGNAL_TYPE = "latent_strong_wallet_entry"


def _fwd_return(entry_price: float | None, future_price: float | None) -> float | None:
    if entry_price is None or future_price is None:
        return None
    return round(future_price - entry_price, 4)


def _parse_db_ts(value: str) -> datetime:
    if value.isdigit():
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        normalized = value.replace(" ", "T")
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


def _to_epoch_seconds(value: datetime) -> int:
    return int(value.timestamp())


def _history_interval(hours: int) -> str:
    if hours in _HISTORY_INTERVAL_BY_HOUR:
        return _HISTORY_INTERVAL_BY_HOUR[hours]
    if hours <= 24:
        return "1h"
    if hours <= 72:
        return "6h"
    return "1d"


def _history_point_to_price(point: Any) -> tuple[int | None, float | None]:
    if isinstance(point, dict):
        ts = point["t"] if "t" in point else point["ts"] if "ts" in point else point.get("timestamp")
        price = point["p"] if "p" in point else point.get("price")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        ts, price = point[0], point[1]
    else:
        return None, None

    try:
        clean_ts = int(ts) if ts is not None else None
    except (TypeError, ValueError):
        clean_ts = None
    try:
        clean_price = float(price) if price is not None else None
    except (TypeError, ValueError):
        clean_price = None
    return clean_ts, clean_price


def _closest_history_price(payload: Dict[str, Any], target_ts: int) -> float | None:
    history = payload.get("history") if isinstance(payload, dict) else None
    if not history:
        return None

    best_price: float | None = None
    best_distance: int | None = None
    for point in history:
        point_ts, point_price = _history_point_to_price(point)
        if point_ts is None or point_price is None:
            continue
        distance = abs(point_ts - target_ts)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_price = point_price
    return best_price


def _official_history_price(
    client: ClobPublicClient,
    *,
    token_id: str | None,
    target_dt: datetime,
    horizon_hours: int,
    cache: Dict[tuple[str, int, str], float | None],
) -> float | None:
    if not token_id:
        return None

    now_utc = datetime.now(timezone.utc)
    if target_dt > now_utc:
        return None

    interval = _history_interval(horizon_hours)
    interval_seconds = _INTERVAL_SECONDS[interval]
    target_ts = _to_epoch_seconds(target_dt)
    cache_key = (token_id, target_ts, interval)
    if cache_key in cache:
        return cache[cache_key]

    try:
        payload = client.get_prices_history(
            token_id,
            interval=interval,
            start_ts=target_ts - interval_seconds,
            end_ts=target_ts + interval_seconds,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Price-history fallback failed for token=%s horizon=%sh target=%s: %s",
            token_id,
            horizon_hours,
            target_dt.isoformat(),
            exc,
        )
        cache[cache_key] = None
        return None

    price = _closest_history_price(payload, target_ts)
    cache[cache_key] = price
    return price


def _resolve_missing_reason(
    *,
    base_ts: str,
    hours_forward: int,
    token_id: str | None,
) -> str:
    target_dt = _parse_db_ts(base_ts) + timedelta(hours=hours_forward)
    if target_dt > datetime.now(timezone.utc):
        return "future_not_reached"
    if not token_id:
        return "missing_token_id"
    return "missing_local_snapshot_and_official_history"


def _snapshot_outcome_price(snapshot: Any | None, outcome: str | None) -> float | None:
    if snapshot is None:
        return None
    lowered = str(outcome or "yes").lower()
    if lowered == "no":
        return snapshot["no_price"]
    return snapshot["yes_price"]


def _token_id_for_outcome(market: Any | None, outcome: str | None) -> str | None:
    if market is None:
        return None
    lowered = str(outcome or "yes").lower()
    if lowered == "no":
        return market["no_token_id"]
    return market["yes_token_id"]


def _resolve_market_price(
    db: Database,
    client: ClobPublicClient,
    *,
    condition_id: str,
    token_id: str | None,
    outcome: str | None,
    base_ts: str,
    hours_forward: int,
    history_cache: Dict[tuple[str, int, str], float | None],
) -> Dict[str, Any]:
    snapshot = db.get_snapshot_at_or_after(condition_id, hours_forward, base_ts)
    snapshot_price = _snapshot_outcome_price(snapshot, outcome)
    if snapshot_price is not None:
        return {
            "price": snapshot_price,
            "source": LOCAL_SNAPSHOT_SOURCE,
            "eligible": True,
            "missing_reason": None,
        }

    target_dt = _parse_db_ts(base_ts) + timedelta(hours=hours_forward)
    history_price = _official_history_price(
        client,
        token_id=token_id,
        target_dt=target_dt,
        horizon_hours=hours_forward,
        cache=history_cache,
    )
    if history_price is not None:
        return {
            "price": history_price,
            "source": OFFICIAL_HISTORY_SOURCE,
            "eligible": True,
            "missing_reason": None,
        }

    return {
        "price": None,
        "source": MISSING_SOURCE,
        "eligible": target_dt <= datetime.now(timezone.utc),
        "missing_reason": _resolve_missing_reason(
            base_ts=base_ts,
            hours_forward=hours_forward,
            token_id=token_id,
        ),
    }


def _resolve_yes_price(
    db: Database,
    client: ClobPublicClient,
    *,
    condition_id: str,
    yes_token_id: str | None,
    base_ts: str,
    hours_forward: int,
    history_cache: Dict[tuple[str, int, str], float | None],
) -> Dict[str, Any]:
    return _resolve_market_price(
        db,
        client,
        condition_id=condition_id,
        token_id=yes_token_id,
        outcome="yes",
        base_ts=base_ts,
        hours_forward=hours_forward,
        history_cache=history_cache,
    )


def _fieldnames(horizons: Sequence[int]) -> List[str]:
    columns = [
        "alert_ts",
        "condition_id",
        "title",
        "market_url",
        "yes_token_id",
        "alert_type",
        "score",
        "score_total",
        "score_price_anomaly",
        "score_holder_concentration",
        "score_wallet_quality",
        "score_trade_flow",
        "severity",
        "confidence",
        "action_label",
        "reason_summary",
        "current_yes_price",
        "price_delta_6h",
        "price_delta_24h",
        "price_delta_72h",
        "entry_yes_price",
        "entry_price_source",
        "entry_eligible",
        "entry_missing_reason",
    ]
    for hours in horizons:
        columns.extend(
            [
                f"fwd_{hours}h_yes_price",
                f"fwd_{hours}h_yes_return",
                f"price_{hours}h_source",
                f"eligible_{hours}h",
                f"missing_reason_{hours}h",
            ]
        )
    return columns


def _latent_fieldnames(horizons: Sequence[int]) -> List[str]:
    columns = [
        "signal_ts",
        "condition_id",
        "title",
        "market_url",
        "wallet_address",
        "outcome",
        "alert_type",
        "score",
        "score_total",
        "severity",
        "confidence",
        "action_label",
        "reason_summary",
        "politics_score",
        "overall_score",
        "wallet_strength",
        "first_trade_ts",
        "first_trade_price",
        "first_trade_notional",
        "buy_trade_count_window",
        "cumulative_buy_notional_window",
        "confirmation_hours",
        "entry_snapshot_ts",
        "entry_outcome_price",
        "signal_snapshot_ts",
        "signal_outcome_price",
        "pre_signal_outcome_move",
        "pre_signal_abs_move",
        "wallet_visible_in_holders",
        "holder_snapshot_ts",
        "market_open_at_signal",
        "hours_to_end_at_signal",
        "entry_price_source",
        "entry_eligible",
        "entry_missing_reason",
    ]
    for hours in horizons:
        columns.extend(
            [
                f"fwd_{hours}h_outcome_price",
                f"fwd_{hours}h_outcome_return",
                f"price_{hours}h_source",
                f"eligible_{hours}h",
                f"missing_reason_{hours}h",
            ]
        )
    return columns


def _normalize_horizons(horizons: Iterable[int] | None, default: Sequence[int]) -> List[int]:
    values = sorted({int(hours) for hours in (horizons or default) if int(hours) >= 0})
    return values or list(default)


def run_backtest(
    db: Database,
    settings: Settings,
    *,
    horizons: Iterable[int] | None = None,
    out_csv: Path | None = None,
) -> List[Dict[str, Any]]:
    resolved_horizons = _normalize_horizons(horizons, DEFAULT_BACKTEST_HORIZONS)
    results: List[Dict[str, Any]] = []
    history_cache: Dict[tuple[str, int, str], float | None] = {}
    history_fallback_hits = 0

    alerts = db.get_alerts()
    if not alerts:
        logger.info("Backtest finished: 0 rows")
        if out_csv:
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            with out_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_fieldnames(resolved_horizons))
                writer.writeheader()
        return results

    clob = ClobPublicClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    try:
        for alert in alerts:
            market = db.get_market_backtest_meta(alert["condition_id"])
            title = market["title"] if market and market["title"] else alert["market_title"]
            yes_token_id = market["yes_token_id"] if market and market["yes_token_id"] else alert["yes_token_id"]

            entry_resolution = _resolve_yes_price(
                db,
                clob,
                condition_id=alert["condition_id"],
                yes_token_id=yes_token_id,
                base_ts=alert["alert_ts"],
                hours_forward=0,
                history_cache=history_cache,
            )
            entry_price = entry_resolution["price"]
            if entry_price is None:
                continue

            if entry_resolution["source"] == OFFICIAL_HISTORY_SOURCE:
                history_fallback_hits += 1

            result = {
                "alert_ts": alert["alert_ts"],
                "condition_id": alert["condition_id"],
                "title": title,
                "market_url": alert["market_url"],
                "yes_token_id": yes_token_id or alert["yes_token_id"],
                "alert_type": alert["alert_type"],
                "score": alert["score"],
                "score_total": alert["score_total"],
                "score_price_anomaly": alert["score_price_anomaly"],
                "score_holder_concentration": alert["score_holder_concentration"],
                "score_wallet_quality": alert["score_wallet_quality"],
                "score_trade_flow": alert["score_trade_flow"],
                "severity": alert["severity"],
                "confidence": alert["confidence"],
                "action_label": alert["action_label"],
                "reason_summary": alert["reason_summary"],
                "current_yes_price": alert["current_yes_price"],
                "price_delta_6h": alert["price_delta_6h"],
                "price_delta_24h": alert["price_delta_24h"],
                "price_delta_72h": alert["price_delta_72h"],
                "entry_yes_price": entry_price,
                "entry_price_source": entry_resolution["source"],
                "entry_eligible": entry_resolution["eligible"],
                "entry_missing_reason": entry_resolution["missing_reason"],
            }

            for hours in resolved_horizons:
                future_resolution = _resolve_yes_price(
                    db,
                    clob,
                    condition_id=alert["condition_id"],
                    yes_token_id=yes_token_id,
                    base_ts=alert["alert_ts"],
                    hours_forward=hours,
                    history_cache=history_cache,
                )
                future_price = future_resolution["price"]
                if future_resolution["source"] == OFFICIAL_HISTORY_SOURCE:
                    history_fallback_hits += 1
                result[f"fwd_{hours}h_yes_price"] = future_price
                result[f"fwd_{hours}h_yes_return"] = _fwd_return(entry_price, future_price)
                result[f"price_{hours}h_source"] = future_resolution["source"]
                result[f"eligible_{hours}h"] = future_resolution["eligible"]
                result[f"missing_reason_{hours}h"] = future_resolution["missing_reason"]

            results.append(result)
    finally:
        clob.close()

    if out_csv:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_fieldnames(resolved_horizons))
            writer.writeheader()
            writer.writerows(results)

    logger.info(
        "Backtest finished: %s rows across horizons=%s, %s official history fallback lookups used",
        len(results),
        ",".join(str(hours) for hours in resolved_horizons),
        history_fallback_hits,
    )
    return results


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _latent_classify_action(score_total: float) -> tuple[str, str]:
    if score_total >= 8.0:
        return "high", "high-priority"
    if score_total >= 5.5:
        return "medium", "review now"
    return "low", "watch"


def _latent_confidence(wallet_strength: float, abs_move: float, buy_trade_count: int, wallet_visible: bool) -> str:
    if wallet_strength >= 80 and abs_move <= 0.03 and (buy_trade_count >= 2 or wallet_visible):
        return "high"
    if wallet_strength >= 60 and abs_move <= 0.05:
        return "medium"
    return "low"


def _latent_signal_score(
    *,
    wallet_strength: float,
    cumulative_buy_notional: float,
    buy_trade_count: int,
    abs_move: float,
    wallet_visible: bool,
) -> float:
    score = 0.0
    if wallet_strength >= 80:
        score += 3.5
    elif wallet_strength >= 60:
        score += 2.5
    if cumulative_buy_notional >= 20_000:
        score += 3.0
    elif cumulative_buy_notional >= 5_000:
        score += 2.0
    elif cumulative_buy_notional >= 1_000:
        score += 1.0
    score += min(2.0, max(0, buy_trade_count - 1) * 0.75)
    if abs_move <= 0.02:
        score += 2.0
    elif abs_move <= 0.05:
        score += 1.0
    if wallet_visible:
        score += 1.0
    return round(score, 2)


def _snapshot_at_or_before(
    snapshots: Sequence[tuple[datetime, Any]],
    target_dt: datetime,
) -> tuple[datetime, Any] | None:
    candidate: tuple[datetime, Any] | None = None
    for snapshot_dt, snapshot in snapshots:
        if snapshot_dt > target_dt:
            break
        candidate = (snapshot_dt, snapshot)
    return candidate


def _snapshot_at_or_after(
    snapshots: Sequence[tuple[datetime, Any]],
    target_dt: datetime,
) -> tuple[datetime, Any] | None:
    for snapshot_dt, snapshot in snapshots:
        if snapshot_dt >= target_dt:
            return snapshot_dt, snapshot
    return None


def _wallet_visible_at_or_after(
    db: Database,
    *,
    condition_id: str,
    base_ts: str,
    wallet_address: str,
) -> tuple[bool, str | None]:
    row = db.conn.execute(
        """
        WITH holder_cycle AS (
            SELECT MIN(snapshot_ts) AS snapshot_ts
            FROM holder_snapshots
            WHERE condition_id = %s
              AND snapshot_ts >= %s
        )
        SELECT
            (SELECT snapshot_ts FROM holder_cycle) AS snapshot_ts,
            EXISTS(
                SELECT 1
                FROM holder_snapshots hs
                WHERE hs.condition_id = %s
                  AND hs.snapshot_ts = (SELECT snapshot_ts FROM holder_cycle)
                  AND LOWER(hs.wallet_address) = LOWER(%s)
            ) AS visible
        """,
        (condition_id, base_ts, condition_id, wallet_address),
    ).fetchone()
    if row is None or row["snapshot_ts"] is None:
        return False, None
    return bool(row["visible"]), row["snapshot_ts"]


def _latent_reason_summary(
    *,
    cumulative_buy_notional: float,
    buy_trade_count: int,
    outcome: str,
    move: float,
    confirmation_hours: int,
    wallet_strength: float,
) -> str:
    return (
        f"Strong wallet accumulated {cumulative_buy_notional:.0f} in {buy_trade_count} "
        f"{outcome.lower()} buy(s) while outcome price moved {move:+.3f} over ~{confirmation_hours}h "
        f"(wallet strength {wallet_strength:.1f})"
    )


def _load_snapshot_cache(db: Database) -> Dict[str, List[tuple[datetime, Any]]]:
    rows = db.conn.execute(
        """
        SELECT condition_id, snapshot_ts, yes_price, no_price
        FROM market_snapshots
        ORDER BY condition_id ASC, snapshot_ts ASC
        """
    ).fetchall()
    cache: Dict[str, List[tuple[datetime, Any]]] = defaultdict(list)
    for row in rows:
        try:
            snapshot_dt = _parse_db_ts(row["snapshot_ts"])
        except ValueError:
            continue
        cache[row["condition_id"]].append((snapshot_dt, row))
    return dict(cache)


def _load_market_meta_map(db: Database) -> Dict[str, Any]:
    rows = db.conn.execute(
        """
        SELECT condition_id, title, yes_token_id, no_token_id, market_url, end_date, closed_time
        FROM markets
        """
    ).fetchall()
    return {row["condition_id"]: row for row in rows}


def _load_latent_trade_groups(db: Database) -> Dict[tuple[str, str, str], List[Dict[str, Any]]]:
    rows = db.conn.execute(
        """
        SELECT
            t.trade_key,
            t.trade_ts,
            t.condition_id,
            t.wallet_address,
            t.outcome,
            t.price,
            t.size,
            t.notional,
            ws.politics_score,
            ws.overall_score
        FROM trades t
        LEFT JOIN wallet_scores ws ON ws.wallet_address = t.wallet_address
        WHERE LOWER(COALESCE(t.side, '')) = 'buy'
          AND t.condition_id IS NOT NULL
          AND t.wallet_address IS NOT NULL
          AND COALESCE(t.outcome, '') IN ('Yes', 'No')
        ORDER BY t.condition_id ASC, t.wallet_address ASC, t.outcome ASC, t.trade_ts ASC, t.trade_key ASC
        """
    ).fetchall()
    grouped: Dict[tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            trade_dt = _parse_db_ts(str(row["trade_ts"]))
        except ValueError:
            continue
        grouped[(row["condition_id"], row["wallet_address"], row["outcome"])].append(
            {
                "trade_key": row["trade_key"],
                "trade_ts": row["trade_ts"],
                "trade_dt": trade_dt,
                "condition_id": row["condition_id"],
                "wallet_address": row["wallet_address"],
                "outcome": row["outcome"],
                "price": row["price"],
                "size": row["size"],
                "notional": float(row["notional"] or 0.0),
                "politics_score": row["politics_score"],
                "overall_score": row["overall_score"],
                "wallet_strength": max(float(row["politics_score"] or 0.0), float(row["overall_score"] or 0.0)),
            }
        )
    return dict(grouped)


def run_latent_entry_backtest(
    db: Database,
    settings: Settings,
    *,
    horizons: Iterable[int] | None = None,
    out_csv: Path | None = None,
    confirmation_hours: int = 24,
    max_pre_signal_drift: float = 0.05,
    min_cumulative_notional: float = 1000.0,
    min_wallet_strength: float = 60.0,
) -> List[Dict[str, Any]]:
    resolved_horizons = _normalize_horizons(horizons, DEFAULT_LATENT_BACKTEST_HORIZONS)
    results: List[Dict[str, Any]] = []
    history_cache: Dict[tuple[str, int, str], float | None] = {}
    history_fallback_hits = 0

    trade_groups = _load_latent_trade_groups(db)
    if not trade_groups:
        logger.info("Latent backtest finished: 0 rows")
        if out_csv:
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            with out_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=_latent_fieldnames(resolved_horizons))
                writer.writeheader()
        return results

    snapshot_cache = _load_snapshot_cache(db)
    market_meta = _load_market_meta_map(db)

    clob = ClobPublicClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    try:
        for (condition_id, wallet_address, outcome), trades in trade_groups.items():
            market = market_meta.get(condition_id)
            snapshots = snapshot_cache.get(condition_id, [])
            if market is None or not snapshots:
                continue

            index = 0
            while index < len(trades):
                first_trade = trades[index]
                signal_target_dt = first_trade["trade_dt"] + timedelta(hours=confirmation_hours)

                window_trades: List[Dict[str, Any]] = []
                next_index = index
                while next_index < len(trades) and trades[next_index]["trade_dt"] <= signal_target_dt:
                    window_trades.append(trades[next_index])
                    next_index += 1

                cumulative_buy_notional = round(sum(item["notional"] for item in window_trades), 2)
                wallet_strength = max((item["wallet_strength"] for item in window_trades), default=0.0)
                if cumulative_buy_notional < min_cumulative_notional or wallet_strength < min_wallet_strength:
                    index = next_index
                    continue

                entry_snapshot_tuple = _snapshot_at_or_before(snapshots, first_trade["trade_dt"])
                signal_snapshot_tuple = _snapshot_at_or_after(snapshots, signal_target_dt)
                if entry_snapshot_tuple is None or signal_snapshot_tuple is None:
                    index = next_index
                    continue

                _, entry_snapshot = entry_snapshot_tuple
                signal_snapshot_dt, signal_snapshot = signal_snapshot_tuple
                entry_outcome_price = _snapshot_outcome_price(entry_snapshot, outcome)
                signal_outcome_price = _snapshot_outcome_price(signal_snapshot, outcome)
                if entry_outcome_price is None or signal_outcome_price is None:
                    index = next_index
                    continue

                pre_signal_move = signal_outcome_price - entry_outcome_price
                pre_signal_abs_move = abs(pre_signal_move)
                end_value = market["closed_time"] or market["end_date"]
                hours_to_end_at_signal = None
                market_open_at_signal = True
                if end_value:
                    try:
                        end_dt = _parse_db_ts(end_value)
                    except ValueError:
                        end_dt = None
                    if end_dt is not None:
                        hours_to_end_at_signal = (end_dt - signal_snapshot_dt).total_seconds() / 3600
                        market_open_at_signal = end_dt > signal_snapshot_dt
                if pre_signal_abs_move > max_pre_signal_drift or not market_open_at_signal:
                    index = next_index
                    continue

                wallet_visible_in_holders, holder_snapshot_ts = _wallet_visible_at_or_after(
                    db,
                    condition_id=condition_id,
                    base_ts=signal_snapshot["snapshot_ts"],
                    wallet_address=wallet_address,
                )
                score_total = _latent_signal_score(
                    wallet_strength=wallet_strength,
                    cumulative_buy_notional=cumulative_buy_notional,
                    buy_trade_count=len(window_trades),
                    abs_move=pre_signal_abs_move,
                    wallet_visible=wallet_visible_in_holders,
                )
                severity, action_label = _latent_classify_action(score_total)
                confidence = _latent_confidence(
                    wallet_strength,
                    pre_signal_abs_move,
                    len(window_trades),
                    wallet_visible_in_holders,
                )
                reason_summary = _latent_reason_summary(
                    cumulative_buy_notional=cumulative_buy_notional,
                    buy_trade_count=len(window_trades),
                    outcome=outcome,
                    move=pre_signal_move,
                    confirmation_hours=confirmation_hours,
                    wallet_strength=wallet_strength,
                )
                token_id = _token_id_for_outcome(market, outcome)
                signal_resolution = _resolve_market_price(
                    db,
                    clob,
                    condition_id=condition_id,
                    token_id=token_id,
                    outcome=outcome,
                    base_ts=signal_snapshot["snapshot_ts"],
                    hours_forward=0,
                    history_cache=history_cache,
                )
                if signal_resolution["source"] == OFFICIAL_HISTORY_SOURCE:
                    history_fallback_hits += 1
                signal_price = signal_resolution["price"]
                if signal_price is None:
                    index = next_index
                    continue

                result = {
                    "signal_ts": signal_snapshot["snapshot_ts"],
                    "condition_id": condition_id,
                    "title": market["title"],
                    "market_url": market["market_url"],
                    "wallet_address": wallet_address,
                    "outcome": outcome,
                    "alert_type": LATENT_SIGNAL_TYPE,
                    "score": score_total,
                    "score_total": score_total,
                    "severity": severity,
                    "confidence": confidence,
                    "action_label": action_label,
                    "reason_summary": reason_summary,
                    "politics_score": _round_or_none(max((item["politics_score"] for item in window_trades if item["politics_score"] is not None), default=None), 2),
                    "overall_score": _round_or_none(max((item["overall_score"] for item in window_trades if item["overall_score"] is not None), default=None), 2),
                    "wallet_strength": _round_or_none(wallet_strength, 2),
                    "first_trade_ts": first_trade["trade_ts"],
                    "first_trade_price": first_trade["price"],
                    "first_trade_notional": first_trade["notional"],
                    "buy_trade_count_window": len(window_trades),
                    "cumulative_buy_notional_window": cumulative_buy_notional,
                    "confirmation_hours": confirmation_hours,
                    "entry_snapshot_ts": entry_snapshot["snapshot_ts"],
                    "entry_outcome_price": entry_outcome_price,
                    "signal_snapshot_ts": signal_snapshot["snapshot_ts"],
                    "signal_outcome_price": signal_price,
                    "pre_signal_outcome_move": _round_or_none(pre_signal_move),
                    "pre_signal_abs_move": _round_or_none(pre_signal_abs_move),
                    "wallet_visible_in_holders": wallet_visible_in_holders,
                    "holder_snapshot_ts": holder_snapshot_ts,
                    "market_open_at_signal": market_open_at_signal,
                    "hours_to_end_at_signal": _round_or_none(hours_to_end_at_signal, 2),
                    "entry_price_source": signal_resolution["source"],
                    "entry_eligible": signal_resolution["eligible"],
                    "entry_missing_reason": signal_resolution["missing_reason"],
                }

                for hours in resolved_horizons:
                    future_resolution = _resolve_market_price(
                        db,
                        clob,
                        condition_id=condition_id,
                        token_id=token_id,
                        outcome=outcome,
                        base_ts=signal_snapshot["snapshot_ts"],
                        hours_forward=hours,
                        history_cache=history_cache,
                    )
                    if future_resolution["source"] == OFFICIAL_HISTORY_SOURCE:
                        history_fallback_hits += 1
                    future_price = future_resolution["price"]
                    result[f"fwd_{hours}h_outcome_price"] = future_price
                    result[f"fwd_{hours}h_outcome_return"] = _fwd_return(signal_price, future_price)
                    result[f"price_{hours}h_source"] = future_resolution["source"]
                    result[f"eligible_{hours}h"] = future_resolution["eligible"]
                    result[f"missing_reason_{hours}h"] = future_resolution["missing_reason"]

                results.append(result)
                index = next_index
    finally:
        clob.close()

    if out_csv:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_latent_fieldnames(resolved_horizons))
            writer.writeheader()
            writer.writerows(results)

    logger.info(
        "Latent backtest finished: %s rows across horizons=%s, confirm=%sh, max_drift=%.3f, min_notional=%.0f, %s official history fallback lookups used",
        len(results),
        ",".join(str(hours) for hours in resolved_horizons),
        confirmation_hours,
        max_pre_signal_drift,
        min_cumulative_notional,
        history_fallback_hits,
    )
    return results
