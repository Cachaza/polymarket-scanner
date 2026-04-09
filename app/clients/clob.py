from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .base import BaseHTTPClient


class ClobPublicClient(BaseHTTPClient):
    def __init__(self, timeout: float, user_agent: str) -> None:
        super().__init__("https://clob.polymarket.com", timeout, user_agent)

    def get_last_trade_prices(self, token_ids: Iterable[str]) -> List[Dict[str, Any]]:
        token_ids = [str(token_id) for token_id in token_ids if token_id]
        if not token_ids:
            return []
        payload = [{"token_id": token_id} for token_id in token_ids]
        return self.post("/last-trades-prices", json=payload)

    def get_prices_history(
        self,
        token_id: str,
        *,
        interval: str = "1h",
        start_ts: int | None = None,
        end_ts: int | None = None,
        fidelity: int | None = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"market": token_id, "interval": interval}
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        if fidelity is not None:
            params["fidelity"] = fidelity
        return self.get("/prices-history", params=params)
