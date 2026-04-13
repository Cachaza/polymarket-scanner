from __future__ import annotations

import json
from typing import Any, Dict

from .models import Alert
from .utils import safe_json_dumps


def normalize_outcome_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "winner_yes", "resolved_yes"}:
            return 1.0
        if lowered in {"no", "false", "winner_no", "resolved_no"}:
            return 0.0
        try:
            parsed = float(lowered)
        except ValueError:
            if "yes" in lowered and "no" not in lowered:
                return 1.0
            if "no" in lowered and "yes" not in lowered:
                return 0.0
            return None
        if 0.0 <= parsed <= 1.0:
            return parsed
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if 0.0 <= parsed <= 1.0 else None
    if isinstance(value, list):
        return normalize_outcome_price(value[0]) if value else None
    if isinstance(value, dict):
        for key in ("yes", "Yes", "YES"):
            if key in value:
                return normalize_outcome_price(value[key])
    return None


def resolved_yes_price(raw_json: str | None, latest_yes_price: float | None) -> float | None:
    if not raw_json:
        if latest_yes_price is not None and (latest_yes_price <= 0.05 or latest_yes_price >= 0.95):
            return round(latest_yes_price, 4)
        return None

    try:
        payload = json.loads(raw_json)
    except Exception:
        payload = {}

    if isinstance(payload, dict):
        for key in ("winningOutcome", "winner", "resolvedOutcome", "resolution", "outcome"):
            candidate = normalize_outcome_price(payload.get(key))
            if candidate is not None:
                return round(candidate, 4)

        candidate = normalize_outcome_price(payload.get("outcomePrices"))
        if candidate is not None:
            return round(candidate, 4)

        tokens = payload.get("tokens") or payload.get("outcomes") or payload.get("outcomeTokens")
        if isinstance(tokens, list):
            for token in tokens:
                if not isinstance(token, dict):
                    continue
                outcome_name = str(token.get("outcome") or token.get("name") or "").strip().lower()
                if outcome_name != "yes":
                    continue
                for key in ("price", "outcomePrice", "winningPrice", "resolvedPrice"):
                    candidate = normalize_outcome_price(token.get(key))
                    if candidate is not None:
                        return round(candidate, 4)

    if latest_yes_price is not None and (latest_yes_price <= 0.05 or latest_yes_price >= 0.95):
        return round(latest_yes_price, 4)
    return None


def recommendation_meta(row: Dict[str, Any]) -> tuple[str, str, float]:
    score_total = float(row.get("score_total") or 0.0)
    watchlist_strength = float(
        int(bool(row.get("price_anomaly_hit")))
        + int(bool(row.get("holder_concentration_hit")))
        + int(bool(row.get("wallet_quality_hit")))
        + int(bool(row.get("history_ready_6h")))
        + int(bool(row.get("trade_enriched")))
        - (0.5 if row.get("warmup_only") else 0.0)
    )
    conviction_score = round(score_total if row.get("source") == "alert" or row.get("alert_ts") else max(0.0, watchlist_strength), 2)

    if row.get("source") == "alert" or row.get("alert_ts"):
        if row.get("severity") == "high" or row.get("confidence") == "high" or score_total >= 8.0:
            return "consider_yes", "actionable", conviction_score
        return "watch_yes", "monitoring", conviction_score
    if row.get("warmup_only"):
        return "wait_for_history", "monitoring", conviction_score
    if row.get("history_ready_6h") and (
        row.get("trade_enriched") or row.get("wallet_quality_hit") or row.get("price_anomaly_hit")
    ):
        return "watch_yes", "monitoring", conviction_score
    return "wait_for_history", "monitoring", conviction_score


def outcome_verdict(entry_price: float | None, final_price: float | None) -> tuple[float | None, str | None]:
    if entry_price in (None, 0) or final_price is None:
        return None, None
    outcome_return = round((final_price - entry_price) / entry_price, 4)
    if outcome_return > 0:
        return outcome_return, "good_call"
    if outcome_return < 0:
        return outcome_return, "bad_call"
    return outcome_return, "flat_call"


def recommendation_from_alert(alert: Alert, *, alert_ts: str) -> Dict[str, Any]:
    recommendation, status, conviction_score = recommendation_meta(
        {
            "source": "alert",
            "severity": alert.severity,
            "confidence": alert.confidence,
            "score_total": alert.score_total,
        }
    )
    return {
        "entry_ts": alert_ts,
        "condition_id": alert.condition_id,
        "source": "alert",
        "market_title": alert.market_title,
        "market_url": alert.market_url,
        "side": "Yes",
        "recommendation": recommendation,
        "status": status,
        "conviction_score": conviction_score,
        "severity": alert.severity,
        "confidence": alert.confidence,
        "reason_summary": alert.reason_summary,
        "entry_yes_price": alert.current_yes_price,
        "history_ready_6h": True,
        "warmup_only": False,
        "trade_enriched": bool(alert.score_trade_flow > 0),
        "source_meta_json": safe_json_dumps(
            {
                "alert_type": alert.alert_type,
                "score": alert.score,
                "score_total": alert.score_total,
                "score_price_anomaly": alert.score_price_anomaly,
                "score_holder_concentration": alert.score_holder_concentration,
                "score_wallet_quality": alert.score_wallet_quality,
                "score_trade_flow": alert.score_trade_flow,
                "reasons_json": alert.reasons_json,
            }
        ),
    }


def recommendation_from_watchlist(row: Dict[str, Any]) -> Dict[str, Any]:
    recommendation, status, conviction_score = recommendation_meta({**row, "source": "watchlist"})
    return {
        "entry_ts": row["snapshot_ts"],
        "condition_id": row["condition_id"],
        "source": "watchlist",
        "market_title": row.get("market_title"),
        "market_url": row.get("market_url"),
        "side": "Yes",
        "recommendation": recommendation,
        "status": status,
        "conviction_score": conviction_score,
        "severity": None,
        "confidence": None,
        "reason_summary": row.get("reason_summary"),
        "entry_yes_price": row.get("current_yes_price"),
        "history_ready_6h": bool(row.get("history_ready_6h")),
        "warmup_only": bool(row.get("warmup_only")),
        "trade_enriched": bool(row.get("trade_enriched")),
        "source_meta_json": safe_json_dumps(
            {
                "price_delta_6h": row.get("price_delta_6h"),
                "yes_top5_seen_share": row.get("yes_top5_seen_share"),
                "price_anomaly_hit": bool(row.get("price_anomaly_hit")),
                "holder_concentration_hit": bool(row.get("holder_concentration_hit")),
                "wallet_quality_hit": bool(row.get("wallet_quality_hit")),
                "component_flags_json": row.get("component_flags_json", {}),
            }
        ),
    }
