from __future__ import annotations

import logging

from ..config import Settings
from ..db import Database
from ..extract import event_to_market_records, market_to_market_record
from ..clients.gamma import GammaClient
from ..utils import chunked

logger = logging.getLogger(__name__)


def _refresh_recommended_market_statuses(settings: Settings, db: Database, client: GammaClient) -> dict[str, int]:
    condition_ids = db.get_unclosed_recommended_condition_ids(limit=settings.market_limit)
    refreshed = 0
    closed = 0

    for batch in chunked(condition_ids, 50):
        for market in client.get_markets_by_condition_ids(batch):
            record = market_to_market_record(market)
            if record is None:
                continue
            db.upsert_market(record)
            refreshed += 1
            if record.closed:
                closed += 1

    return {
        "recommended_markets_checked": len(condition_ids),
        "recommended_markets_refreshed": refreshed,
        "recommended_markets_closed": closed,
    }


def run(settings: Settings, db: Database) -> dict[str, int]:
    client = GammaClient(timeout=settings.request_timeout, user_agent=settings.user_agent)
    try:
        count_events = 0
        count_markets = 0
        for event in client.iter_active_events(limit=min(settings.discovery_limit, 100)):
            count_events += 1
            db.upsert_event(event)
            for market in event_to_market_records(event, settings.keywords):
                db.upsert_market(market)
                count_markets += 1
            if count_events >= settings.discovery_limit:
                break
        recommended_status = _refresh_recommended_market_statuses(settings, db, client)
        db.commit()
        logger.info(
            "Discover finished: %s events, %s scoped markets, %s recommended markets refreshed, %s newly closed",
            count_events,
            count_markets,
            recommended_status["recommended_markets_refreshed"],
            recommended_status["recommended_markets_closed"],
        )
        return {"events": count_events, "markets": count_markets, **recommended_status}
    finally:
        client.close()
