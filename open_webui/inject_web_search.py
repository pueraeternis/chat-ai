"""Inject chat-proxy ``web_search`` system tool into Open WebUI request bodies.

Used by unit tests; keep in sync with ``functions/proxy_web_search_filter.py`` (OWUI sandbox has no repo imports).
"""

from __future__ import annotations

import copy
from typing import Any, Literal

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


def has_web_search_tool(tools: list[dict[str, Any]]) -> bool:
    return any(t.get("type") == WEB_SEARCH_TYPE for t in tools)


def has_function_tool(tools: list[dict[str, Any]]) -> bool:
    return any(t.get("type") == FUNCTION_TYPE for t in tools)


def web_search_feature_enabled(body: dict[str, Any]) -> bool:
    features = body.get("features")
    if not isinstance(features, dict):
        return False
    return bool(features.get("web_search"))


def build_web_search_tool(
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


def should_skip_web_search_injection(
    body: dict[str, Any],
    *,
    require_web_search_feature: bool,
) -> bool:
    tools = _tools_list(body)
    if has_web_search_tool(tools):
        return True
    if has_function_tool(tools):
        return True
    return require_web_search_feature and not web_search_feature_enabled(body)


def inject_web_search(
    body: dict[str, Any],
    *,
    country: str = "RU",
    city: str = "Saint Petersburg",
    region: str = "Leningrad Oblast",
    timezone: str = "Europe/Moscow",
    search_context_size: SearchContextSize = "medium",
    require_web_search_feature: bool = False,
) -> dict[str, Any]:
    """Return *body* unchanged or a copy with ``web_search`` appended to ``tools``."""
    if should_skip_web_search_injection(
        body,
        require_web_search_feature=require_web_search_feature,
    ):
        return body

    tool = build_web_search_tool(
        country=country,
        city=city,
        region=region,
        timezone=timezone,
        search_context_size=search_context_size,
    )
    out = copy.deepcopy(body)
    existing = out.get("tools")
    if isinstance(existing, list):
        out["tools"] = [*existing, tool]
    else:
        out["tools"] = [tool]
    return out
