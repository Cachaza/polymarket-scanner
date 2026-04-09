from __future__ import annotations

from typing import Iterable


def normalize_text(*parts: str | None) -> str:
    return " ".join((part or "").strip().lower() for part in parts if part)


def matches_keywords(text: str, keywords: Iterable[str]) -> bool:
    haystack = text.lower()
    return any(keyword.lower() in haystack for keyword in keywords)
