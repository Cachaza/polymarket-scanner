from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import httpx

from .clients.clob import ClobPublicClient
from .config import Settings
from .db import Database

logger = logging.getLogger(__name__)

DEFAULT_BACKTEST_HORIZONS = (6, 24, 72)
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


def _fwd_return(entry_price: float | None, future_price: float | None) -> float | None:
    if entry_price is None or future_price is None:
        return None
    return future_price - entry_price


def _parse_db_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


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
    yes_token_id: str | None,
) -> str:
    target_dt = _parse_db_ts(base_ts) + timedelta(hours=hours_forward)
    if target_dt > datetime.now(timezone.utc):
        return "future_not_reached"
    if not yes_token_id:
        return "missing_yes_token_id"
    return "missing_local_snapshot_and_official_history"


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
    snapshot = db.get_snapshot_at_or_after(condition_id, hours_forward, base_ts)
    if snapshot and snapshot["yes_price"] is not None:
        return {
            "price": snapshot["yes_price"],
            "source": LOCAL_SNAPSHOT_SOURCE,
            "eligible": True,
            "missing_reason": None,
        }

    target_dt = _parse_db_ts(base_ts) + timedelta(hours=hours_forward)
    history_price = _official_history_price(
        client,
        token_id=yes_token_id,
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
            yes_token_id=yes_token_id,
        ),
    }


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


def _normalize_horizons(horizons: Iterable[int] | None) -> List[int]:
    values = sorted({int(hours) for hours in (horizons or DEFAULT_BACKTEST_HORIZONS) if int(hours) >= 0})
    return values or list(DEFAULT_BACKTEST_HORIZONS)


def run_backtest(
    db: Database,
    settings: Settings,
    *,
    horizons: Iterable[int] | None = None,
    out_csv: Path | None = None,
) -> List[Dict[str, Any]]:
    resolved_horizons = _normalize_horizons(horizons)
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
