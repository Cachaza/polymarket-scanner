from __future__ import annotations

import logging

from ..config import Settings
from ..db import Database
from ..extract import event_to_market_records
from ..clients.gamma import GammaClient

logger = logging.getLogger(__name__)


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
        db.commit()
        logger.info("Discover finished: %s events, %s scoped markets", count_events, count_markets)
        return {"events": count_events, "markets": count_markets}
    finally:
        client.close()
