"""Temporal grounding system prompt for web_search final LLM step."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC_TIMEZONE = "UTC"

_WEB_SEARCH_SYSTEM_TEMPLATE = (
    "Today's date is {date_iso} (timezone {timezone}).\n\n"
    "You will receive web search results in a tool message below. "
    "Treat them as current factual context from the live web, not as hypothetical "
    "or futuristic fiction.\n\n"
    "Your training data may be outdated. Do not claim that source publication dates "
    'are "from the future" or that news is fake solely because dates are later than '
    'your internal assumptions about the current year. The date line above is '
    'authoritative for what "today" means.\n\n'
    "Answer the user's question using the provided sources. If the sources do not "
    "support a confident answer, say so clearly."
)


def resolve_timezone(user_location: dict[str, Any]) -> str:
    """Return IANA timezone from user_location, or UTC when missing or invalid."""
    approximate = user_location.get("approximate")
    if not isinstance(approximate, dict):
        return UTC_TIMEZONE
    tz_name = approximate.get("timezone")
    if not isinstance(tz_name, str) or not tz_name.strip():
        return UTC_TIMEZONE
    try:
        ZoneInfo(tz_name.strip())
    except ZoneInfoNotFoundError:
        return UTC_TIMEZONE
    return tz_name.strip()


def build_web_search_system_prompt(*, now: datetime, timezone: str) -> str:
    """Build English system prompt with today's date in the given timezone."""
    tz = ZoneInfo(timezone)
    if now.tzinfo is None:
        local_now = now.replace(tzinfo=UTC).astimezone(tz)
    else:
        local_now = now.astimezone(tz)
    date_iso = local_now.date().isoformat()
    return _WEB_SEARCH_SYSTEM_TEMPLATE.format(date_iso=date_iso, timezone=timezone)


def prepend_web_search_system(
    messages: list[dict[str, Any]],
    user_location: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Prepend proxy system message for temporal grounding (final answer only)."""
    timezone = resolve_timezone(user_location)
    instant = now if now is not None else datetime.now(UTC)
    system_content = build_web_search_system_prompt(now=instant, timezone=timezone)
    return [{"role": "system", "content": system_content}, *messages]
