from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .base import BaseHTTPClient


class DataAPIClient(BaseHTTPClient):
    def __init__(self, timeout: float, user_agent: str) -> None:
        super().__init__("https://data-api.polymarket.com", timeout, user_agent)

    def get_top_holders(self, condition_ids: Iterable[str], limit: int = 20, min_balance: int = 1) -> List[Dict[str, Any]]:
        market = ",".join(condition_ids)
        return self.get("/holders", params={"market": market, "limit": limit, "minBalance": min_balance})

    def get_trades(
        self,
        *,
        markets: Iterable[str] | None = None,
        user: str | None = None,
        limit: int = 100,
        offset: int = 0,
        taker_only: bool = True,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "takerOnly": str(taker_only).lower()}
        if markets:
            params["market"] = ",".join(markets)
        if user:
            params["user"] = user
        return self.get("/trades", params=params)

    def get_leaderboard(
        self,
        *,
        category: str = "POLITICS",
        time_period: str = "ALL",
        order_by: str = "PNL",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return self.get(
            "/v1/leaderboard",
            params={
                "category": category,
                "timePeriod": time_period,
                "orderBy": order_by,
                "limit": limit,
                "offset": offset,
            },
        )
