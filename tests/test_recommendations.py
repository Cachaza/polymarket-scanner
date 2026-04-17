from __future__ import annotations

import json

from app.extract import market_to_market_record
from app.recommendations import recommendation_from_watchlist, resolved_side_price, resolved_yes_price


def test_resolved_yes_price_parses_gamma_outcome_prices_json_string() -> None:
    raw_json = json.dumps({"outcomePrices": '["1", "0"]'})

    assert resolved_yes_price(raw_json, latest_yes_price=None) == 1.0


def test_standalone_gamma_market_keeps_resolution_payload() -> None:
    market = {
        "id": "market-1",
        "conditionId": "cond-1",
        "question": "Will this resolve yes?",
        "slug": "will-this-resolve-yes",
        "closed": True,
        "closedTime": "2026-04-17T10:00:00Z",
        "outcomePrices": '["0", "1"]',
        "clobTokenIds": '["yes-token", "no-token"]',
        "events": [{"id": "event-1", "slug": "event-slug", "active": False, "closed": True}],
    }

    record = market_to_market_record(market)

    assert record is not None
    assert record.condition_id == "cond-1"
    assert record.closed is True
    assert record.closed_time == "2026-04-17T10:00:00Z"
    assert record.market_url == "https://polymarket.com/event/event-slug"
    assert resolved_yes_price(record.raw_json, latest_yes_price=None) == 0.0


def test_resolved_side_price_inverts_yes_resolution_for_no_side() -> None:
    raw_json = json.dumps({"outcomePrices": '["0", "1"]'})

    assert resolved_side_price(raw_json, latest_yes_price=None, side="No") == 1.0


def test_watchlist_recommendation_can_target_no_side() -> None:
    recommendation = recommendation_from_watchlist(
        {
            "snapshot_ts": "2026-04-17 10:00:00",
            "condition_id": "cond-no",
            "market_title": "Fixture NO Market",
            "market_url": "https://polymarket.com/event/fixture-no",
            "side": "No",
            "current_yes_price": 0.41,
            "current_no_price": 0.59,
            "price_anomaly_hit": True,
            "holder_concentration_hit": False,
            "wallet_quality_hit": True,
            "history_ready_6h": True,
            "warmup_only": False,
            "trade_enriched": True,
            "reason_summary": "No: price anomaly, wallet quality (history-ready)",
            "component_flags_json": {"side": "No"},
        }
    )

    assert recommendation["side"] == "No"
    assert recommendation["recommendation"] == "watch_no"
    assert recommendation["entry_price"] == 0.59
    assert recommendation["entry_yes_price"] == 0.41
