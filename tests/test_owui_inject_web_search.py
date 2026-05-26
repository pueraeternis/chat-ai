"""Unit tests for Open WebUI web_search tool injection."""

from __future__ import annotations

from typing import Any

import pytest
from inject_web_search import (
    build_web_search_tool,
    inject_web_search,
    should_skip_web_search_injection,
)


@pytest.mark.parametrize(
    ("body", "require_feature", "expected_skip"),
    [
        (
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "web_search", "user_location": {"approximate": {"country": "US"}}}],
            },
            False,
            True,
        ),
        (
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": "x", "parameters": {}}}],
            },
            False,
            True,
        ),
        (
            {"messages": [{"role": "user", "content": "hi"}]},
            True,
            True,
        ),
        (
            {
                "messages": [{"role": "user", "content": "hi"}],
                "features": {"web_search": True},
            },
            True,
            False,
        ),
        (
            {"messages": [{"role": "user", "content": "hi"}]},
            False,
            False,
        ),
    ],
)
def test_should_skip(
    body: dict[str, Any],
    require_feature: bool,
    expected_skip: bool,
) -> None:
    assert (
        should_skip_web_search_injection(
            body,
            require_web_search_feature=require_feature,
        )
        is expected_skip
    )


def test_inject_appends_tool_with_defaults() -> None:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "content": "новости"}],
        "stream": True,
    }
    out = inject_web_search(body)
    assert out is not body
    assert body.get("tools") is None
    tools = out["tools"]
    assert len(tools) == 1
    assert tools[0] == build_web_search_tool(
        country="RU",
        city="Saint Petersburg",
        region="Leningrad Oblast",
        timezone="Europe/Moscow",
        search_context_size="medium",
    )


def test_inject_preserves_existing_tools() -> None:
    body = {
        "messages": [{"role": "user", "content": "q"}],
        "tools": [{"type": "other", "name": "future"}],
    }
    out = inject_web_search(body)
    assert len(out["tools"]) == 2
    assert out["tools"][0]["type"] == "other"
    assert out["tools"][1]["type"] == "web_search"


def test_inject_custom_valves() -> None:
    out = inject_web_search(
        {"messages": [{"role": "user", "content": "weather"}]},
        country="US",
        city="San Francisco",
        region="California",
        timezone="America/Los_Angeles",
        search_context_size="low",
    )
    tool = out["tools"][0]
    assert tool["search_context_size"] == "low"
    approx = tool["user_location"]["approximate"]
    assert approx["country"] == "US"
    assert approx["city"] == "San Francisco"


def test_inject_unchanged_when_web_search_present() -> None:
    body = {
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "type": "web_search",
                "user_location": {
                    "type": "approximate",
                    "approximate": {"country": "DE"},
                },
            },
        ],
    }
    assert inject_web_search(body) is body


def test_inject_unchanged_when_function_tools() -> None:
    body = {
        "messages": [{"role": "user", "content": "x"}],
        "tools": [{"type": "function", "function": {"name": "fn", "parameters": {}}}],
    }
    assert inject_web_search(body) is body


def test_inject_with_require_feature_and_owui_toggle() -> None:
    body = {
        "messages": [{"role": "user", "content": "news"}],
        "features": {"web_search": True},
    }
    out = inject_web_search(body, require_web_search_feature=True)
    assert out["tools"][0]["type"] == "web_search"
