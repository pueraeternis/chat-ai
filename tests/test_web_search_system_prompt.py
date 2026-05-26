"""Tests for web_search final-answer temporal grounding prompt."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from operations.web_search_prompt import (
    UTC_TIMEZONE,
    build_web_search_system_prompt,
    prepend_web_search_system,
    resolve_timezone,
)


def _user_location(*, timezone: str = "America/New_York") -> dict:
    return {
        "type": "approximate",
        "approximate": {
            "country": "US",
            "city": "New York",
            "region": "New York",
            "timezone": timezone,
        },
    }


def test_resolve_timezone_from_user_location() -> None:
    assert resolve_timezone(_user_location(timezone="America/New_York")) == "America/New_York"


def test_resolve_timezone_missing_fallback_utc() -> None:
    assert resolve_timezone({}) == UTC_TIMEZONE
    assert resolve_timezone({"approximate": {}}) == UTC_TIMEZONE


def test_resolve_timezone_invalid_fallback_utc() -> None:
    assert resolve_timezone(_user_location(timezone="Not/A/Zone")) == UTC_TIMEZONE


def test_build_prompt_includes_date_and_timezone() -> None:
    now = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    prompt = build_web_search_system_prompt(now=now, timezone="America/New_York")
    assert "Today's date is 2026-05-26 (timezone America/New_York)." in prompt
    assert "live web" in prompt
    assert '"from the future"' in prompt


def test_build_prompt_date_follows_timezone() -> None:
    # 2026-05-26 22:00 UTC is still 2026-05-27 in Tokyo
    now = datetime(2026, 5, 26, 22, 0, tzinfo=UTC)
    prompt = build_web_search_system_prompt(now=now, timezone="Asia/Tokyo")
    assert "Today's date is 2026-05-27 (timezone Asia/Tokyo)." in prompt


def test_prepend_inserts_system_first() -> None:
    now = datetime(2026, 5, 26, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    messages = [{"role": "user", "content": "News?"}]
    out = prepend_web_search_system(messages, _user_location(), now=now)
    assert out[0]["role"] == "system"
    assert "2026-05-26" in out[0]["content"]
    assert out[1] == messages[0]
