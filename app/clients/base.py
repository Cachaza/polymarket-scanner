from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class BaseHTTPClient:
    def __init__(self, base_url: str, timeout: float, user_agent: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code == 403:
                    sleep_for = (15, 45, 45)[attempt]
                else:
                    sleep_for = 0.5 * (attempt + 1)
                logger.warning("GET %s failed on attempt %s: %s", url, attempt + 1, exc)
                time.sleep(sleep_for)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"GET {url} failed without exception")

    def post(self, path: str, json: Any | None = None) -> Any:
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.post(url, json=json)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                sleep_for = 0.5 * (attempt + 1)
                logger.warning("POST %s failed on attempt %s: %s", url, attempt + 1, exc)
                time.sleep(sleep_for)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"POST {url} failed without exception")

    def close(self) -> None:
        self.client.close()
