from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Tuple

from .keywords import matches_keywords, normalize_text
from .models import MarketRecord
from .utils import build_market_url, safe_json_dumps


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [value]
    return [value]


def extract_yes_no_token_ids(market: Dict[str, Any]) -> Tuple[str | None, str | None]:
    # Common patterns seen in Polymarket responses:
    # - clobTokenIds: JSON string or list with [yes, no]
    # - outcomes / tokens arrays
    clob_token_ids = _as_list(market.get("clobTokenIds") or market.get("clob_token_ids"))
    if len(clob_token_ids) >= 2:
        return str(clob_token_ids[0]), str(clob_token_ids[1])

    token_candidates = _as_list(market.get("tokens") or market.get("outcomeTokens") or market.get("tokenIds"))
    if len(token_candidates) >= 2 and all(isinstance(item, (str, int)) for item in token_candidates):
        return str(token_candidates[0]), str(token_candidates[1])

    if token_candidates and all(isinstance(item, dict) for item in token_candidates):
        yes = None
        no = None
        for token in token_candidates:
            outcome = str(token.get("outcome") or token.get("name") or "").strip().lower()
            token_id = token.get("tokenId") or token.get("id") or token.get("asset")
            if not token_id:
                continue
            if outcome == "yes":
                yes = str(token_id)
            elif outcome == "no":
                no = str(token_id)
        return yes, no

    return None, None


def extract_condition_id(market: Dict[str, Any]) -> str | None:
    return market.get("conditionId") or market.get("condition_id")


def extract_end_date(event: Dict[str, Any], market: Dict[str, Any]) -> str | None:
    return (
        market.get("endDate")
        or market.get("umaEndDate")
        or market.get("closedTime")
        or event.get("endDate")
    )


def extract_reward_asset_address(market: Dict[str, Any]) -> str | None:
    rewards = _as_list(market.get("clobRewards"))
    for reward in rewards:
        if not isinstance(reward, dict):
            continue
        asset_address = reward.get("assetAddress")
        if asset_address:
            return str(asset_address)
    return None


def market_text_blob(event: Dict[str, Any], market: Dict[str, Any]) -> str:
    return normalize_text(
        event.get("title"),
        event.get("description"),
        event.get("category"),
        event.get("subcategory"),
        market.get("question"),
        market.get("title"),
        market.get("marketTitle"),
        market.get("description"),
    )


def _first_market_event(market: Dict[str, Any]) -> Dict[str, Any]:
    for event in _as_list(market.get("events")):
        if isinstance(event, dict):
            return event
    return {}


def market_to_market_record(market: Dict[str, Any], event: Dict[str, Any] | None = None) -> MarketRecord | None:
    event = event or _first_market_event(market)
    condition_id = extract_condition_id(market)
    if not condition_id:
        return None

    yes_token_id, no_token_id = extract_yes_no_token_ids(market)
    event_slug = event.get("slug") or market.get("eventSlug") or market.get("event_slug")
    return MarketRecord(
        condition_id=str(condition_id),
        event_id=str(event.get("id")) if event.get("id") is not None else None,
        event_slug=event_slug,
        slug=market.get("slug"),
        market_id=str(market.get("id")) if market.get("id") is not None else None,
        question_id=str(market.get("questionID")) if market.get("questionID") is not None else None,
        market_url=build_market_url(event_slug, market.get("slug")),
        title=str(market.get("question") or market.get("title") or market.get("marketTitle") or "Untitled market"),
        description=market.get("description") or event.get("description"),
        category=market.get("category") or event.get("category"),
        active=bool(market.get("active", event.get("active", True))),
        closed=bool(market.get("closed", event.get("closed", False))),
        archived=bool(market.get("archived", event.get("archived", False))),
        accepting_orders=bool(market["acceptingOrders"]) if "acceptingOrders" in market else None,
        end_date=extract_end_date(event, market),
        closed_time=market.get("closedTime"),
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        image_url=market.get("image") or market.get("icon") or event.get("image") or event.get("icon"),
        reward_asset_address=extract_reward_asset_address(market),
        raw_json=safe_json_dumps(market),
    )


def event_to_market_records(event: Dict[str, Any], keywords: Iterable[str]) -> List[MarketRecord]:
    out: List[MarketRecord] = []
    for market in event.get("markets", []) or []:
        blob = market_text_blob(event, market)
        if not matches_keywords(blob, keywords):
            continue
        record = market_to_market_record(market, event)
        if record is not None:
            out.append(record)
    return out


def build_holder_rows(
    *,
    condition_id: str,
    snapshot_ts: str,
    holder_payload: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for token_entry in holder_payload:
        token_id = str(token_entry.get("token"))
        holders = token_entry.get("holders", []) or []
        for idx, holder in enumerate(holders, start=1):
            wallet_address = str(holder.get("proxyWallet") or "").lower()
            if not wallet_address:
                continue
            rows.append(
                {
                    "condition_id": condition_id,
                    "snapshot_ts": snapshot_ts,
                    "token_id": token_id,
                    "wallet_address": wallet_address,
                    "amount": holder.get("amount"),
                    "outcome_index": holder.get("outcomeIndex"),
                    "rank": idx,
                    "raw_json": holder,
                }
            )
    return rows
