from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .models import Alert
from .utils import safe_json_dumps


def pct_move(new: float | None, old: float | None) -> float | None:
    if new is None or old is None:
        return None
    return new - old


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _wallet_strength(wallet_row: Any | None) -> float:
    if not wallet_row:
        return 0.0
    politics_score = float(wallet_row["politics_score"] or 0)
    overall_score = float(wallet_row["overall_score"] or 0)
    return max(politics_score, overall_score)


def _normalize_side(value: str | None) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def _classify_action(score_total: float) -> tuple[str, str]:
    if score_total >= 8.0:
        return "high", "high-priority"
    if score_total >= 5.5:
        return "medium", "review now"
    return "low", "watch"


def _classify_confidence(triggered_components: int, strong_wallets_count: int, fresh_taker_wallets_count: int) -> str:
    if strong_wallets_count >= 1 and triggered_components >= 2:
        return "high"
    if triggered_components >= 3 or fresh_taker_wallets_count >= 2:
        return "medium"
    return "low"


def _trade_flow_metrics(
    trades: Sequence[Dict[str, Any]],
    *,
    yes_token_id: str | None,
    holders_24h: Sequence[str],
    wallet_scores: Dict[str, Any],
) -> Dict[str, Any]:
    if not trades:
        return {
            "recent_trade_count": 0,
            "yes_trade_count": 0,
            "buy_count": 0,
            "sell_count": 0,
            "buy_notional": 0.0,
            "sell_notional": 0.0,
            "net_buy_notional": 0.0,
            "recent_trade_wallets": 0,
            "fresh_taker_wallets": 0,
            "strong_trade_wallets": 0,
            "summary": "No recent enriched taker flow",
            "score": 0.0,
            "reasons": [],
        }

    holder_set_24h = set(holders_24h)
    yes_outcome_trades = [
        trade for trade in trades
        if (yes_token_id and trade.get("token_id") == yes_token_id)
        or _normalize_side(trade.get("outcome")) == "yes"
    ]
    scoped_trades = yes_outcome_trades or list(trades)

    buy_count = 0
    sell_count = 0
    buy_notional = 0.0
    sell_notional = 0.0
    trade_wallets = set()
    fresh_takers = set()
    strong_trade_wallets = set()

    for trade in scoped_trades:
        wallet = str(trade.get("wallet_address") or "").lower()
        if wallet:
            trade_wallets.add(wallet)
            if wallet not in holder_set_24h:
                fresh_takers.add(wallet)
            if _wallet_strength(wallet_scores.get(wallet)) >= 60:
                strong_trade_wallets.add(wallet)

        notional = float(trade.get("notional") or 0)
        side = _normalize_side(trade.get("side"))
        if side == "buy":
            buy_count += 1
            buy_notional += notional
        elif side == "sell":
            sell_count += 1
            sell_notional += notional

    reasons: List[str] = []
    score_trade_flow = 0.0
    net_buy_notional = buy_notional - sell_notional
    if buy_count >= 3 and buy_count > sell_count:
        score_trade_flow += 1.5
        reasons.append(f"recent taker flow skewed buy ({buy_count} buys vs {sell_count} sells)")
    if net_buy_notional > 0 and buy_notional >= max(1.5 * sell_notional, 25):
        score_trade_flow += 1.5
        reasons.append(f"net taker notional favored buys by {net_buy_notional:+.2f}")
    if len(fresh_takers) >= 2:
        score_trade_flow += 1.0
        reasons.append(f"{len(fresh_takers)} fresh taker wallet(s) in recent flow")
    if strong_trade_wallets:
        score_trade_flow += 2.0
        reasons.append(f"{len(strong_trade_wallets)} strong wallet(s) appeared in taker flow")

    if reasons:
        summary = "; ".join(reasons[:2])
    else:
        summary = "Recent taker flow was balanced or thin"

    return {
        "recent_trade_count": len(trades),
        "yes_trade_count": len(scoped_trades),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "buy_notional": round(buy_notional, 2),
        "sell_notional": round(sell_notional, 2),
        "net_buy_notional": round(net_buy_notional, 2),
        "recent_trade_wallets": len(trade_wallets),
        "fresh_taker_wallets": len(fresh_takers),
        "strong_trade_wallets": len(strong_trade_wallets),
        "summary": summary,
        "score": round(score_trade_flow, 2),
        "reasons": reasons,
    }


def _reason_summary(
    *,
    price_delta_6h: float | None,
    concentration_delta_24h: float | None,
    strong_wallets_count: int,
    fresh_taker_wallets_count: int,
    score_trade_flow: float,
) -> str:
    price_flat = price_delta_6h is not None and abs(price_delta_6h) < 0.03
    short_term_dip = price_delta_6h is not None and price_delta_6h <= -0.05
    concentration_spike = concentration_delta_24h is not None and concentration_delta_24h >= 0.10

    if strong_wallets_count >= 1 and price_flat:
        return "High-quality wallets accumulated while price stayed flat"
    if concentration_spike and fresh_taker_wallets_count >= 1:
        return "Concentration spike with fresh taker flow"
    if strong_wallets_count >= 1 and short_term_dip:
        return "Strong wallets buying into a short-term dip"
    if strong_wallets_count >= 1 and score_trade_flow >= 1.5:
        return "Strong wallets accumulated into one-sided recent flow"
    if concentration_spike:
        return "Holder concentration rose quickly over the last 24h"
    if score_trade_flow >= 2.0:
        return "Recent taker flow turned decisively one-sided"
    if price_delta_6h is not None:
        return f"Yes price moved sharply over the last 6h ({price_delta_6h:+.3f})"
    return "Multiple anomaly components triggered together"


def score_market(
    *,
    condition_id: str,
    market_title: str,
    market_url: str | None,
    yes_token_id: str | None,
    title: str,
    latest: Dict[str, Any],
    prev_6h: Dict[str, Any] | None,
    prev_24h: Dict[str, Any] | None,
    prev_72h: Dict[str, Any] | None,
    latest_holders: List[str],
    holders_24h: List[str],
    wallet_scores: Dict[str, Any],
    recent_trades: Sequence[Dict[str, Any]],
) -> Alert | None:
    price_delta_6h = pct_move(latest.get("yes_price"), prev_6h.get("yes_price")) if prev_6h else None
    price_delta_24h = pct_move(latest.get("yes_price"), prev_24h.get("yes_price")) if prev_24h else None
    price_delta_72h = pct_move(latest.get("yes_price"), prev_72h.get("yes_price")) if prev_72h else None

    score_price_anomaly = 0.0
    score_holder_concentration = 0.0
    score_wallet_quality = 0.0
    reasons: List[str] = []
    if price_delta_6h is not None and abs(price_delta_6h) >= 0.10:
        score_price_anomaly += 3.0
        reasons.append(f"yes price moved {price_delta_6h:+.3f} in ~6h")
    elif price_delta_24h is not None and abs(price_delta_24h) >= 0.12:
        score_price_anomaly += 2.0
        reasons.append(f"yes price drifted {price_delta_24h:+.3f} in ~24h")
    elif price_delta_72h is not None and abs(price_delta_72h) >= 0.18:
        score_price_anomaly += 1.0
        reasons.append(f"yes price repriced {price_delta_72h:+.3f} in ~72h")

    yes_top5_delta_24h = None
    if prev_24h:
        current_yes_top5 = latest.get("yes_top5_seen_share")
        prev_yes_top5 = prev_24h.get("yes_top5_seen_share")
        if current_yes_top5 is not None and prev_yes_top5 is not None:
            yes_top5_delta_24h = current_yes_top5 - prev_yes_top5
            if yes_top5_delta_24h >= 0.10:
                score_holder_concentration += 2.0
                reasons.append(f"yes top-5 observed share increased by {yes_top5_delta_24h:+.3f} in ~24h")
        current_no_top5 = latest.get("no_top5_seen_share")
        prev_no_top5 = prev_24h.get("no_top5_seen_share")
        if current_no_top5 is not None and prev_no_top5 is not None and current_no_top5 - prev_no_top5 >= 0.10:
            score_holder_concentration += 1.0
            reasons.append(f"no top-5 observed share increased by {current_no_top5 - prev_no_top5:+.3f} in ~24h")

    if (latest.get("yes_top5_seen_share") or 0) >= 0.75:
        score_holder_concentration += 1.0
        reasons.append(f"yes top-5 observed share is elevated at {latest['yes_top5_seen_share']:.3f}")

    new_wallets = sorted(set(latest_holders) - set(holders_24h))
    if len(new_wallets) >= 2:
        score_wallet_quality += 1.5
        reasons.append(f"{len(new_wallets)} new holder wallet(s) vs ~24h ago")

    strong_wallets = [
        wallet for wallet in new_wallets
        if _wallet_strength(wallet_scores.get(wallet)) >= 60
    ]
    if strong_wallets:
        score_wallet_quality += 4.0
        reasons.append(f"{len(strong_wallets)} strong wallet(s) entered")

    if latest.get("observed_holder_wallets", 0) <= 3 and latest.get("yes_top_holder_amount"):
        score_holder_concentration += 1.0
        reasons.append("very concentrated observed holder set")

    holder_strength_by_wallet = {
        wallet: _wallet_strength(wallet_scores.get(wallet))
        for wallet in latest_holders
    }
    current_holder_strengths = [
        score
        for score in holder_strength_by_wallet.values()
        if score >= 60
    ]
    if len(current_holder_strengths) >= 2:
        score_wallet_quality += 1.0
        reasons.append(f"{len(current_holder_strengths)} strong wallet(s) now present in holders")

    trade_metrics = _trade_flow_metrics(
        recent_trades,
        yes_token_id=yes_token_id,
        holders_24h=holders_24h,
        wallet_scores=wallet_scores,
    )
    score_trade_flow = float(trade_metrics["score"])
    reasons.extend(trade_metrics["reasons"])

    score_total = score_price_anomaly + score_holder_concentration + score_wallet_quality + score_trade_flow
    if score_total < 4.0:
        return None

    if score_wallet_quality >= max(score_price_anomaly, score_holder_concentration, score_trade_flow):
        alert_type = "smart_wallet_entry"
    elif score_holder_concentration >= max(score_price_anomaly, score_trade_flow):
        alert_type = "holder_concentration_shift"
    elif score_trade_flow >= score_price_anomaly:
        alert_type = "trade_flow_shift"
    elif new_wallets and (latest.get("yes_top_holder_amount") or 0) > 0:
        alert_type = "new_wallet_holder_jump"
    else:
        alert_type = "price_dislocation"

    severity, action_label = _classify_action(score_total)
    triggered_components = sum(
        1
        for component_score in (
            score_price_anomaly,
            score_holder_concentration,
            score_wallet_quality,
            score_trade_flow,
        )
        if component_score > 0
    )
    confidence = _classify_confidence(
        triggered_components,
        len(strong_wallets),
        int(trade_metrics["fresh_taker_wallets"]),
    )
    reason_summary = _reason_summary(
        price_delta_6h=price_delta_6h,
        concentration_delta_24h=yes_top5_delta_24h,
        strong_wallets_count=len(strong_wallets),
        fresh_taker_wallets_count=int(trade_metrics["fresh_taker_wallets"]),
        score_trade_flow=score_trade_flow,
    )
    summary = f"{title}: {reason_summary}"

    holder_concentration_metrics = {
        "yes_top5_seen_share": _round_or_none(latest.get("yes_top5_seen_share")),
        "no_top5_seen_share": _round_or_none(latest.get("no_top5_seen_share")),
        "yes_top5_delta_24h": _round_or_none(yes_top5_delta_24h),
        "observed_holder_wallets": latest.get("observed_holder_wallets"),
        "yes_top_holder_amount": _round_or_none(latest.get("yes_top_holder_amount"), 2),
    }
    wallet_quality_metrics = {
        "new_wallet_count": len(new_wallets),
        "strong_new_wallet_count": len(strong_wallets),
        "strong_current_holder_count": len(current_holder_strengths),
        "max_new_wallet_score": _round_or_none(
            max((_wallet_strength(wallet_scores.get(wallet)) for wallet in new_wallets), default=0.0),
            2,
        ),
        "avg_strong_holder_score": _round_or_none(
            (
                sum(current_holder_strengths) / len(current_holder_strengths)
                if current_holder_strengths else None
            ),
            2,
        ),
    }
    trigger_breakdown = {
        "price_anomaly": {
            "triggered": score_price_anomaly > 0,
            "score": round(score_price_anomaly, 2),
        },
        "holder_concentration": {
            "triggered": score_holder_concentration > 0,
            "score": round(score_holder_concentration, 2),
        },
        "wallet_quality": {
            "triggered": score_wallet_quality > 0,
            "score": round(score_wallet_quality, 2),
        },
        "trade_flow": {
            "triggered": score_trade_flow > 0,
            "score": round(score_trade_flow, 2),
        },
    }
    return Alert(
        condition_id=condition_id,
        alert_type=alert_type,
        score=round(score_total, 2),
        score_total=round(score_total, 2),
        score_price_anomaly=round(score_price_anomaly, 2),
        score_holder_concentration=round(score_holder_concentration, 2),
        score_wallet_quality=round(score_wallet_quality, 2),
        score_trade_flow=round(score_trade_flow, 2),
        market_title=market_title,
        market_url=market_url,
        yes_token_id=yes_token_id,
        current_yes_price=_round_or_none(latest.get("yes_price")),
        price_delta_6h=_round_or_none(price_delta_6h),
        price_delta_24h=_round_or_none(price_delta_24h),
        price_delta_72h=_round_or_none(price_delta_72h),
        severity=severity,
        confidence=confidence,
        action_label=action_label,
        reason_summary=reason_summary,
        summary=summary,
        reasons_json=safe_json_dumps(
            {
                "market": {
                    "title": market_title,
                    "url": market_url,
                    "yes_token_id": yes_token_id,
                },
                "price": {
                    "current_yes_price": _round_or_none(latest.get("yes_price")),
                    "delta_6h": _round_or_none(price_delta_6h),
                    "delta_24h": _round_or_none(price_delta_24h),
                    "delta_72h": _round_or_none(price_delta_72h),
                },
                "holder_concentration_metrics": holder_concentration_metrics,
                "wallet_quality_metrics": wallet_quality_metrics,
                "trade_enrichment_summary": trade_metrics,
                "trigger_breakdown": trigger_breakdown,
                "reason_summary": reason_summary,
                "reasons": reasons,
                "new_wallets": new_wallets,
                "strong_wallets": strong_wallets,
            }
        ),
    )
