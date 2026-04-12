from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

from ..clients.data_api import DataAPIClient
from ..config import Settings
from ..db import Database
from ..utils import utc_now_iso

logger = logging.getLogger(__name__)


def _extract_wallet_entries(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "leaderboard", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def run(settings: Settings, db: Database) -> dict[str, int]:
    client = DataAPIClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    snapshot_ts = utc_now_iso()
    try:
        combos = [
            ("POLITICS", "ALL", "PNL"),
            ("POLITICS", "MONTH", "PNL"),
            ("POLITICS", "ALL", "VOL"),
            ("OVERALL", "ALL", "PNL"),
            ("OVERALL", "ALL", "VOL"),
        ]
        seen_wallets = 0
        for category, time_period, order_by in combos:
            payload = client.get_leaderboard(category=category, time_period=time_period, order_by=order_by, limit=50, offset=0)
            entries = _extract_wallet_entries(payload)
            for idx, entry in enumerate(entries, start=1):
                wallet = (
                    entry.get("walletAddress")
                    or entry.get("proxyWallet")
                    or entry.get("address")
                    or entry.get("user")
                )
                if not wallet:
                    continue
                score_value = entry.get("pnl") or entry.get("volume") or entry.get("score")
                db.upsert_wallet_score(
                    wallet_address=str(wallet).lower(),
                    snapshot_ts=snapshot_ts,
                    category=category,
                    time_period=time_period,
                    order_by=order_by,
                    rank=entry.get("rank") or idx,
                    score_value=float(score_value) if score_value is not None else None,
                    raw_json=entry,
                )
                seen_wallets += 1
        db.update_wallet_summary_fields()
        db.commit()
        logger.info("Leaderboard refresh finished: %s wallet score rows processed", seen_wallets)
        return {"wallet_score_rows": seen_wallets}
    finally:
        client.close()
