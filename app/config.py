from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


DEFAULT_KEYWORDS = [
    "trump",
    "white house",
    "congress",
    "senate",
    "house",
    "supreme court",
    "doj",
    "department of justice",
    "treasury",
    "fed",
    "federal reserve",
    "tariff",
    "sanctions",
    "iran",
    "venezuela",
    "maduro",
    "ukraine",
    "nato",
    "cabinet",
    "executive order",
    "republican",
    "democrat",
    "president",
    "sec",
    "china",
    "trade deal",
]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("POLY_DATABASE_URL", "postgresql://polymarket:polymarket@localhost:5432/polymarket")
    backtest_csv_path: Path = Path(os.getenv("POLY_BACKTEST_CSV_PATH", "data/backtest.csv"))
    latent_backtest_csv_path: Path = Path(os.getenv("POLY_LATENT_BACKTEST_CSV_PATH", "data/latent_backtest.csv"))
    request_timeout: float = float(os.getenv("POLY_REQUEST_TIMEOUT", "20"))
    discovery_limit: int = int(os.getenv("POLY_DISCOVERY_LIMIT", "200"))
    market_limit: int = int(os.getenv("POLY_MARKET_LIMIT", "250"))
    holder_limit: int = int(os.getenv("POLY_HOLDER_LIMIT", "20"))
    holder_min_balance: int = int(os.getenv("POLY_HOLDER_MIN_BALANCE", "1"))
    keyword_mode: str = os.getenv("POLY_KEYWORD_MODE", "keywords")
    keywords: List[str] = field(
        default_factory=lambda: _split_csv(os.getenv("POLY_KEYWORDS", "")) or DEFAULT_KEYWORDS
    )
    telegram_bot_token: str = os.getenv("POLY_TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("POLY_TELEGRAM_CHAT_ID", "")
    user_agent: str = "polymarket-anomaly-scanner/0.1"


def get_settings() -> Settings:
    return Settings()
