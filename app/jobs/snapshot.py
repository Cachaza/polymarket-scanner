from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Iterable, List

import httpx

from ..clients.clob import ClobPublicClient
from ..clients.data_api import DataAPIClient
from ..config import Settings
from ..db import Database
from ..extract import build_holder_rows
from ..recommendations import recommendation_from_watchlist
from ..utils import chunked, synthetic_trade_key, utc_now_iso

logger = logging.getLogger(__name__)

HOLDERS_BATCH_SIZE = 5
HOLDERS_REQUEST_DELAY_BASE = 0.35
HOLDERS_REQUEST_DELAY_JITTER = 0.25
PRICE_ANOMALY_THRESHOLD = 0.10
HOLDER_CONCENTRATION_THRESHOLD = 0.10
WALLET_QUALITY_THRESHOLD = 60.0
TRADE_ENRICHMENT_LIMIT = 25


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _group_holders_by_token(payload: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for entry in payload:
        token_id = str(entry.get("token"))
        out[token_id] = entry.get("holders", []) or []
    return out


def _top5_seen_share(holders: List[Dict[str, Any]]) -> float | None:
    amounts = [_to_float(holder.get("amount")) for holder in holders]
    clean = [value for value in amounts if value is not None]
    if not clean:
        return None
    total_seen = sum(clean)
    if total_seen <= 0:
        return None
    return sum(clean[:5]) / total_seen


def _top_amount(holders: List[Dict[str, Any]]) -> float | None:
    if not holders:
        return None
    return _to_float(holders[0].get("amount"))


def _observed_wallet_count(*holder_lists: List[Dict[str, Any]]) -> int:
    wallets = set()
    for holder_list in holder_lists:
        for holder in holder_list:
            wallet = holder.get("proxyWallet")
            if wallet:
                wallets.add(str(wallet).lower())
    return len(wallets)


def _price_delta(latest_snapshot: Dict[str, Any], prev_snapshot: Dict[str, Any] | None, key: str) -> float | None:
    if not prev_snapshot:
        return None
    old_price = prev_snapshot[key]
    new_price = latest_snapshot.get(key)
    if old_price is None or new_price is None:
        return None
    return new_price - old_price


def _price_anomaly_side(yes_delta: float | None, no_delta: float | None) -> str | None:
    candidates = []
    if yes_delta is not None and abs(yes_delta) >= PRICE_ANOMALY_THRESHOLD:
        candidates.append(("Yes" if yes_delta > 0 else "No", abs(yes_delta)))
    if no_delta is not None and abs(no_delta) >= PRICE_ANOMALY_THRESHOLD:
        candidates.append(("No" if no_delta > 0 else "Yes", abs(no_delta)))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])[0]


def _holder_concentration_delta(
    latest_snapshot: Dict[str, Any],
    prev_snapshot: Dict[str, Any] | None,
    key: str,
) -> float | None:
    if not prev_snapshot:
        return None
    old_top = prev_snapshot[key]
    new_top = latest_snapshot.get(key)
    if old_top is None or new_top is None:
        return None
    return new_top - old_top


def _holder_concentration_side(yes_delta: float | None, no_delta: float | None) -> str | None:
    candidates = []
    if yes_delta is not None and yes_delta >= HOLDER_CONCENTRATION_THRESHOLD:
        candidates.append(("Yes", yes_delta))
    if no_delta is not None and no_delta >= HOLDER_CONCENTRATION_THRESHOLD:
        candidates.append(("No", no_delta))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])[0]


def _holder_wallet_addresses(*holder_lists: List[Dict[str, Any]]) -> List[str]:
    wallets = []
    seen = set()
    for holder_list in holder_lists:
        for holder in holder_list:
            wallet = str(holder.get("proxyWallet") or "").lower()
            if wallet and wallet not in seen:
                seen.add(wallet)
                wallets.append(wallet)
    return wallets


def _passes_wallet_quality(wallet_addresses: Iterable[str], wallet_scores: Dict[str, Any]) -> bool:
    for wallet in wallet_addresses:
        score_row = wallet_scores.get(wallet)
        if not score_row:
            continue
        politics_score = score_row["politics_score"] or 0
        overall_score = score_row["overall_score"] or 0
        if politics_score >= WALLET_QUALITY_THRESHOLD or overall_score >= WALLET_QUALITY_THRESHOLD:
            return True
    return False


def _choose_watchlist_side(
    *,
    price_side: str | None,
    holder_side: str | None,
    yes_wallet_quality_hit: bool,
    no_wallet_quality_hit: bool,
) -> str:
    side_scores = {"Yes": 0, "No": 0}
    if price_side:
        side_scores[price_side] += 1
    if holder_side:
        side_scores[holder_side] += 2
    if yes_wallet_quality_hit:
        side_scores["Yes"] += 2
    if no_wallet_quality_hit:
        side_scores["No"] += 2
    if side_scores["No"] > side_scores["Yes"]:
        return "No"
    return "Yes"


def _has_local_history(prev_snapshot: Dict[str, Any] | None) -> bool:
    return prev_snapshot is not None


def _watchlist_reason_summary(
    *,
    side: str,
    price_anomaly_hit: bool,
    holder_concentration_hit: bool,
    wallet_quality_hit: bool,
    history_ready_6h: bool,
) -> str:
    reasons: List[str] = []
    if price_anomaly_hit:
        reasons.append("price anomaly")
    if holder_concentration_hit:
        reasons.append("holder concentration")
    if wallet_quality_hit:
        reasons.append("wallet quality")
    if not reasons:
        return "watchlist candidate"
    suffix = "history-ready" if history_ready_6h else "warm-up"
    return f"{side}: {', '.join(reasons)} ({suffix})"


def _normalize_trade_rows(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for trade in trades:
        wallet = str(trade.get("proxyWallet") or "").lower() or None
        price = _to_float(trade.get("price"))
        size = _to_float(trade.get("size"))
        out.append(
            {
                "trade_key": synthetic_trade_key(
                    trade.get("transactionHash"),
                    wallet,
                    trade.get("conditionId"),
                    trade.get("timestamp"),
                    trade.get("side"),
                    size,
                    price,
                    trade.get("outcome"),
                ),
                "trade_ts": trade.get("timestamp"),
                "condition_id": trade.get("conditionId"),
                "token_id": trade.get("asset"),
                "wallet_address": wallet,
                "side": trade.get("side"),
                "price": price,
                "size": size,
                "notional": (price or 0) * (size or 0) if price is not None and size is not None else None,
                "tx_hash": trade.get("transactionHash"),
                "title": trade.get("title"),
                "outcome": trade.get("outcome"),
                "raw_json": trade,
            }
        )
    return out


def run(settings: Settings, db: Database) -> dict[str, int]:
    market_rows = db.get_active_markets(limit=settings.market_limit)
    if not market_rows:
        logger.info("No active markets in DB. Run discover first.")
        return {"markets": 0, "holder_rows": 0, "watchlist_candidates": 0, "trade_enriched": 0}

    clob = ClobPublicClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    data_api = DataAPIClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    snapshot_ts = utc_now_iso()

    try:
        token_ids = []
        for row in market_rows:
            if row["yes_token_id"]:
                token_ids.append(row["yes_token_id"])
            if row["no_token_id"]:
                token_ids.append(row["no_token_id"])

        price_map: Dict[str, Dict[str, Any]] = {}
        for batch in chunked(token_ids, 500):
            for item in clob.get_last_trade_prices(batch):
                price_map[str(item.get("token_id"))] = item

        condition_ids = [row["condition_id"] for row in market_rows]
        holders_by_condition: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        holder_rows_to_insert: List[Dict[str, Any]] = []
        for batch in chunked(condition_ids, HOLDERS_BATCH_SIZE):
            try:
                payload = data_api.get_top_holders(batch, limit=settings.holder_limit, min_balance=settings.holder_min_balance)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code == 403:
                    logger.warning("Skipping holders batch after repeated 403 cooldowns: %s", ",".join(batch))
                    continue
                raise
            # Endpoint returns token-based groups, so split using our market token mapping
            by_token = _group_holders_by_token(payload)
            for market in market_rows:
                if market["condition_id"] not in batch:
                    continue
                yes_holders = by_token.get(market["yes_token_id"], [])
                no_holders = by_token.get(market["no_token_id"], [])
                holders_by_condition[market["condition_id"]] = {
                    "yes": yes_holders,
                    "no": no_holders,
                }
                holder_rows_to_insert.extend(
                    build_holder_rows(
                        condition_id=market["condition_id"],
                        snapshot_ts=snapshot_ts,
                        holder_payload=[
                            {"token": market["yes_token_id"], "holders": yes_holders},
                            {"token": market["no_token_id"], "holders": no_holders},
                        ],
                    )
                )
            time.sleep(HOLDERS_REQUEST_DELAY_BASE + random.random() * HOLDERS_REQUEST_DELAY_JITTER)

        db.insert_holder_snapshot_rows(holder_rows_to_insert)

        holder_wallets_by_condition = {
            condition_id: _holder_wallet_addresses(holder_info["yes"], holder_info["no"])
            for condition_id, holder_info in holders_by_condition.items()
        }
        all_holder_wallets = sorted(
            {
                wallet
                for wallet_addresses in holder_wallets_by_condition.values()
                for wallet in wallet_addresses
            }
        )
        wallet_scores = db.get_wallet_scores(all_holder_wallets)

        watchlist_condition_ids: List[str] = []
        watchlist_rows: Dict[str, Dict[str, Any]] = {}
        price_anomaly_count = 0
        holder_concentration_count = 0
        wallet_quality_count = 0
        watchlist_warmup_count = 0
        watchlist_history_ready_count = 0

        for market in market_rows:
            yes_info = price_map.get(market["yes_token_id"], {})
            no_info = price_map.get(market["no_token_id"], {})
            holder_info = holders_by_condition.get(market["condition_id"], {"yes": [], "no": []})

            snapshot = {
                "condition_id": market["condition_id"],
                "snapshot_ts": snapshot_ts,
                "yes_price": _to_float(yes_info.get("price")),
                "no_price": _to_float(no_info.get("price")),
                "yes_side": yes_info.get("side"),
                "no_side": no_info.get("side"),
                "yes_holder_count": len(holder_info["yes"]),
                "no_holder_count": len(holder_info["no"]),
                "yes_top_holder_amount": _top_amount(holder_info["yes"]),
                "no_top_holder_amount": _top_amount(holder_info["no"]),
                "yes_top5_seen_share": _top5_seen_share(holder_info["yes"]),
                "no_top5_seen_share": _top5_seen_share(holder_info["no"]),
                "observed_holder_wallets": _observed_wallet_count(holder_info["yes"], holder_info["no"]),
                "raw_json": {
                    "yes_price": yes_info,
                    "no_price": no_info,
                    "holders": holder_info,
                },
            }
            db.insert_market_snapshot(snapshot)
            prev_snapshot = db.get_snapshot_before(market["condition_id"], snapshot_ts, 6)
            yes_price_delta = _price_delta(snapshot, prev_snapshot, "yes_price")
            no_price_delta = _price_delta(snapshot, prev_snapshot, "no_price")
            price_side = _price_anomaly_side(yes_price_delta, no_price_delta)
            price_anomaly_pass = price_side is not None

            yes_top5_delta = _holder_concentration_delta(snapshot, prev_snapshot, "yes_top5_seen_share")
            no_top5_delta = _holder_concentration_delta(snapshot, prev_snapshot, "no_top5_seen_share")
            holder_side = _holder_concentration_side(yes_top5_delta, no_top5_delta)
            holder_concentration_pass = holder_side is not None

            yes_wallet_quality_pass = _passes_wallet_quality(_holder_wallet_addresses(holder_info["yes"]), wallet_scores)
            no_wallet_quality_pass = _passes_wallet_quality(_holder_wallet_addresses(holder_info["no"]), wallet_scores)
            wallet_quality_pass = yes_wallet_quality_pass or no_wallet_quality_pass
            recommendation_side = _choose_watchlist_side(
                price_side=price_side,
                holder_side=holder_side,
                yes_wallet_quality_hit=yes_wallet_quality_pass,
                no_wallet_quality_hit=no_wallet_quality_pass,
            )

            if price_anomaly_pass:
                price_anomaly_count += 1
            if holder_concentration_pass:
                holder_concentration_count += 1
            if wallet_quality_pass:
                wallet_quality_count += 1

            if price_anomaly_pass or holder_concentration_pass or wallet_quality_pass:
                watchlist_condition_ids.append(market["condition_id"])
                history_ready_6h = _has_local_history(prev_snapshot)
                if history_ready_6h:
                    watchlist_history_ready_count += 1
                else:
                    watchlist_warmup_count += 1
                watchlist_row = {
                    "snapshot_ts": snapshot_ts,
                    "condition_id": market["condition_id"],
                    "market_title": market["title"],
                    "market_url": market.get("market_url"),
                    "side": recommendation_side,
                    "current_yes_price": snapshot.get("yes_price"),
                    "current_no_price": snapshot.get("no_price"),
                    "price_delta_6h": yes_price_delta,
                    "no_price_delta_6h": no_price_delta,
                    "yes_top5_seen_share": snapshot.get("yes_top5_seen_share"),
                    "no_top5_seen_share": snapshot.get("no_top5_seen_share"),
                    "price_anomaly_hit": price_anomaly_pass,
                    "holder_concentration_hit": holder_concentration_pass,
                    "wallet_quality_hit": wallet_quality_pass,
                    "warmup_only": not history_ready_6h,
                    "history_ready_6h": history_ready_6h,
                    "trade_enriched": False,
                    "reason_summary": _watchlist_reason_summary(
                        side=recommendation_side,
                        price_anomaly_hit=price_anomaly_pass,
                        holder_concentration_hit=holder_concentration_pass,
                        wallet_quality_hit=wallet_quality_pass,
                        history_ready_6h=history_ready_6h,
                    ),
                    "component_flags_json": {
                        "side": recommendation_side,
                        "price_anomaly": price_anomaly_pass,
                        "price_anomaly_side": price_side,
                        "holder_concentration": holder_concentration_pass,
                        "holder_concentration_side": holder_side,
                        "wallet_quality": wallet_quality_pass,
                        "yes_wallet_quality": yes_wallet_quality_pass,
                        "no_wallet_quality": no_wallet_quality_pass,
                        "history_ready_6h": history_ready_6h,
                    },
                }
                watchlist_rows[market["condition_id"]] = watchlist_row
                db.insert_watchlist_candidate(watchlist_row)

        # Enrich watchlist candidates, including warm-up markets, to build context cheaply.
        enriched_condition_ids = watchlist_condition_ids[:TRADE_ENRICHMENT_LIMIT]
        for condition_id in enriched_condition_ids:
            trades = data_api.get_trades(markets=[condition_id], limit=50, offset=0, taker_only=True)
            db.insert_trades(_normalize_trade_rows(trades))
            if condition_id in watchlist_rows:
                watchlist_rows[condition_id]["trade_enriched"] = True
            db.conn.execute(
                '''
                UPDATE watchlist_candidates
                SET trade_enriched = 1
                WHERE condition_id = %s AND snapshot_ts = %s
                ''',
                (condition_id, snapshot_ts),
            )

        for row in watchlist_rows.values():
            db.insert_recommendation(recommendation_from_watchlist(row))

        db.commit()
        logger.info(
            "Watchlist funnel: %s price anomaly, %s holder concentration, %s wallet quality, %s watchlist candidates, %s history-ready, %s warmup-only, %s enriched with trades",
            price_anomaly_count,
            holder_concentration_count,
            wallet_quality_count,
            len(watchlist_condition_ids),
            watchlist_history_ready_count,
            watchlist_warmup_count,
            len(enriched_condition_ids),
        )
        logger.info(
            "Snapshot finished: %s markets, %s holder rows, %s watchlist markets enriched with trades",
            len(market_rows),
            len(holder_rows_to_insert),
            len(enriched_condition_ids),
        )
        return {
            "markets": len(market_rows),
            "holder_rows": len(holder_rows_to_insert),
            "watchlist_candidates": len(watchlist_condition_ids),
            "trade_enriched": len(enriched_condition_ids),
            "recommendations": len(watchlist_rows),
        }
    finally:
        clob.close()
        data_api.close()
