"""Map user text to SearXNG language tags (en / ru)."""

from __future__ import annotations

import re
from typing import Any

# SearXNG language tags (see searx/sxng_locales.py): ``en``, ``ru``, not city names.
SEARXNG_LOCALE_EN = "en"
SEARXNG_LOCALE_RU = "ru"

_CYRILLIC = re.compile(r"[\u0400-\u04FF\u0500-\u052F]")
_LATIN = re.compile(r"[A-Za-z]")


def searxng_locale_from_text(text: str) -> str:
    """
    Choose SearXNG ``language`` for metasearch.

    - Cyrillic letters dominate (or tie with Latin) → ``ru``
    - Latin letters present, Cyrillic not dominant → ``en``
    - No letters (digits, emoji, CJK, …) → ``en``
    """
    cyrillic = len(_CYRILLIC.findall(text))
    latin = len(_LATIN.findall(text))
    if cyrillic > 0 and cyrillic >= latin:
        return SEARXNG_LOCALE_RU
    return SEARXNG_LOCALE_EN


def searxng_locale_from_messages(messages: list[dict[str, Any]]) -> str:
    """Detect locale from the last user message text."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        text = _message_text(msg.get("content"))
        if text.strip():
            return searxng_locale_from_text(text)
    return SEARXNG_LOCALE_EN


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        ]
        return " ".join(parts)
    return ""
