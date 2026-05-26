"""
title: Proxy Web Search
author: chat-ai
version: 0.1.0
description: Inject chat-proxy hosted web_search when this filter is enabled in chat.
"""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import BaseModel, Field

# Keep inject helpers in sync with open_webui/inject_web_search.py (OWUI sandbox cannot import repo modules).

WEB_SEARCH_TYPE = "web_search"
FUNCTION_TYPE = "function"

SearchContextSize = Literal["low", "medium", "high"]


def _tools_list(body: dict[str, Any]) -> list[dict[str, Any]]:
    tools = body.get("tools")
    if tools is None:
        return []
    if not isinstance(tools, list):
        return []
    return [t for t in tools if isinstance(t, dict)]


def _has_web_search_tool(tools: list[dict[str, Any]]) -> bool:
    return any(t.get("type") == WEB_SEARCH_TYPE for t in tools)


def _has_function_tool(tools: list[dict[str, Any]]) -> bool:
    return any(t.get("type") == FUNCTION_TYPE for t in tools)


def _web_search_feature_enabled(body: dict[str, Any]) -> bool:
    features = body.get("features")
    if not isinstance(features, dict):
        return False
    return bool(features.get("web_search"))


def _build_web_search_tool(
    *,
    country: str,
    city: str,
    region: str,
    timezone: str,
    search_context_size: SearchContextSize,
) -> dict[str, Any]:
    return {
        "type": WEB_SEARCH_TYPE,
        "search_context_size": search_context_size,
        "user_location": {
            "type": "approximate",
            "approximate": {
                "country": country,
                "city": city,
                "region": region,
                "timezone": timezone,
            },
        },
    }


class Filter:
    """Open WebUI filter: append proxy ``web_search`` to the chat completion body."""

    class Valves(BaseModel):
        country: str = Field(
            default="US",
            description="ISO country for user_location (OpenAI tool contract; not SearXNG locale)",
        )
        city: str = Field(
            default="New York",
            description="Approximate city for user_location",
        )
        region: str = Field(
            default="New York",
            description="Approximate region for user_location",
        )
        timezone: str = Field(
            default="America/New_York",
            description="IANA timezone for user_location",
        )
        search_context_size: SearchContextSize = Field(
            default="medium",
            description="Proxy web_search budget: low | medium | high",
        )
        require_web_search_feature: bool = Field(
            default=False,
            description=(
                "If true, inject only when body.features.web_search is set "
                "(OWUI Web Search icon)"
            ),
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(
        self,
        body: dict,
        __user__: dict | None = None,
    ) -> dict:
        return _inject_web_search_body(body, self.valves)


def _inject_web_search_body(body: dict[str, Any], valves: Filter.Valves) -> dict[str, Any]:
    tools = _tools_list(body)
    if _has_web_search_tool(tools):
        return body
    if _has_function_tool(tools):
        return body
    if valves.require_web_search_feature and not _web_search_feature_enabled(body):
        return body

    tool = _build_web_search_tool(
        country=valves.country,
        city=valves.city,
        region=valves.region,
        timezone=valves.timezone,
        search_context_size=valves.search_context_size,
    )
    out = copy.deepcopy(body)
    existing = out.get("tools")
    if isinstance(existing, list):
        out["tools"] = [*existing, tool]
    else:
        out["tools"] = [tool]
    return out
