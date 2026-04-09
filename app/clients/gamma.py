from __future__ import annotations

from typing import Any, Dict, Iterator, List

from .base import BaseHTTPClient


class GammaClient(BaseHTTPClient):
    def __init__(self, timeout: float, user_agent: str) -> None:
        super().__init__("https://gamma-api.polymarket.com", timeout, user_agent)

    def list_events(self, **params: Any) -> List[Dict[str, Any]]:
        return self.get("/events", params=params)

    def iter_active_events(self, limit: int = 100, order: str = "volume24hr") -> Iterator[Dict[str, Any]]:
        offset = 0
        while True:
            batch = self.list_events(
                active=True,
                closed=False,
                limit=limit,
                offset=offset,
                order=order,
                ascending=False,
            )
            if not batch:
                return
            for item in batch:
                yield item
            if len(batch) < limit:
                return
            offset += limit
