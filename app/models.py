from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketRecord:
    condition_id: str
    event_id: str | None
    event_slug: str | None
    slug: str | None
    title: str
    description: str | None
    category: str | None
    active: bool
    closed: bool
    archived: bool
    end_date: str | None
    yes_token_id: str | None
    no_token_id: str | None
    raw_json: str


@dataclass
class Alert:
    condition_id: str
    alert_type: str
    score: float
    score_total: float
    score_price_anomaly: float
    score_holder_concentration: float
    score_wallet_quality: float
    score_trade_flow: float
    market_title: str | None
    market_url: str | None
    yes_token_id: str | None
    current_yes_price: float | None
    price_delta_6h: float | None
    price_delta_24h: float | None
    price_delta_72h: float | None
    severity: str
    confidence: str
    action_label: str
    reason_summary: str
    summary: str
    reasons_json: str
