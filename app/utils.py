from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, List, Sequence


def utc_now_iso() -> str:
    # Store UTC timestamps in a SQLite-friendly lexical format.
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def chunked(items: Sequence[Any], size: int) -> Iterator[List[Any]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def safe_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_market_url(event_slug: str | None, market_slug: str | None) -> str | None:
    slug = event_slug or market_slug
    if not slug:
        return None
    return f"https://polymarket.com/event/{slug}"


def synthetic_trade_key(
    tx_hash: str | None,
    wallet: str | None,
    condition_id: str | None,
    timestamp: int | str | None,
    side: str | None,
    size: Any,
    price: Any,
    outcome: str | None,
) -> str:
    payload = "|".join(
        [
            tx_hash or "",
            wallet or "",
            condition_id or "",
            str(timestamp or ""),
            side or "",
            str(size),
            str(price),
            outcome or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
