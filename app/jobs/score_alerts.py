from __future__ import annotations
import logging

from ..alerts.telegram import send_telegram_message
from ..config import Settings
from ..db import Database
from ..scoring import score_market
from ..utils import build_market_url, utc_now_iso

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def run(settings: Settings, db: Database) -> None:
    markets = db.get_active_markets(limit=settings.market_limit)
    alert_ts = utc_now_iso()
    history_ready_count = 0
    warmup_skipped_count = 0
    inserted_alerts = 0

    for market in markets:
        latest = db.get_latest_snapshot(market["condition_id"])
        if not latest:
            continue
        prev_6h = db.get_snapshot_before(market["condition_id"], latest["snapshot_ts"], 6)
        prev_24h = db.get_snapshot_before(market["condition_id"], latest["snapshot_ts"], 24)
        prev_72h = db.get_snapshot_before(market["condition_id"], latest["snapshot_ts"], 72)

        latest_holders = db.get_latest_holder_addresses(market["condition_id"])
        holders_24h = db.get_holder_addresses_before(market["condition_id"], latest["snapshot_ts"], 24)
        if not prev_24h or not holders_24h:
            warmup_skipped_count += 1
            continue
        history_ready_count += 1
        recent_trades = [_row_to_dict(row) for row in db.get_recent_trades(market["condition_id"], limit=50)]
        trade_wallets = [trade["wallet_address"] for trade in recent_trades if trade.get("wallet_address")]
        wallet_scores = db.get_wallet_scores(list(set(latest_holders) | set(trade_wallets)))

        alert = score_market(
            condition_id=market["condition_id"],
            market_title=market["title"],
            market_url=build_market_url(market["event_slug"], market["slug"]),
            yes_token_id=market["yes_token_id"],
            title=market["title"],
            latest=_row_to_dict(latest),
            prev_6h=_row_to_dict(prev_6h) if prev_6h else None,
            prev_24h=_row_to_dict(prev_24h) if prev_24h else None,
            prev_72h=_row_to_dict(prev_72h) if prev_72h else None,
            latest_holders=latest_holders,
            holders_24h=holders_24h,
            wallet_scores=wallet_scores,
            recent_trades=recent_trades,
        )
        if alert is not None:
            db.insert_alert(alert, alert_ts)
            inserted_alerts += 1

    db.commit()

    unsent = db.get_unsent_alerts()
    sent_count = 0
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram not configured; skipping all alert sends")
    else:
        for row in unsent:
            title = row["title"] or row["condition_id"]
            text = (
                f"[{row['action_label']}] [{row['alert_type']}] {title}\n"
                f"severity={row['severity']} confidence={row['confidence']} score={row['score_total']}\n"
                f"yes={row['current_yes_price']} 6h={row['price_delta_6h']} 24h={row['price_delta_24h']} 72h={row['price_delta_72h']}\n"
                f"components price={row['score_price_anomaly']} holder={row['score_holder_concentration']} wallet={row['score_wallet_quality']} trade={row['score_trade_flow']}\n"
                f"{row['reason_summary']}\n"
                f"{row['market_url'] or ''}"
            )
            was_sent = send_telegram_message(settings.telegram_bot_token, settings.telegram_chat_id, text)
            if was_sent:
                db.mark_alert_sent(row["id"])
                sent_count += 1
    db.commit()
    logger.info(
        "Score alerts finished: %s history-ready, %s warmup-skipped, %s new alerts, %s sent",
        history_ready_count,
        warmup_skipped_count,
        inserted_alerts,
        sent_count,
    )
