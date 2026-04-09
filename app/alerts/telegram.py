from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token or not chat_id:
        logger.info("Telegram not configured; skipping alert send")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    response.raise_for_status()
    return True
