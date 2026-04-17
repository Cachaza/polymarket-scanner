from __future__ import annotations

import json

from app.extract import market_to_market_record
from app.recommendations import resolved_yes_price


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
