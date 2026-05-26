"""Structured log events for chat-proxy."""

from __future__ import annotations

import logging
from typing import Any

from core.request_context import get_request_id

MAX_QUERY_LOG_CHARS = 200
MAX_URLS_LOG = 10

_LOG_RECORD_SKIP = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
    | {
        "message",
        "msg",
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "stack_info",
        "stacklevel",
        "taskName",
    },
)


def truncate_query(query: str, *, max_chars: int = MAX_QUERY_LOG_CHARS) -> str:
    """Truncate router/search query for logs."""
    text = query.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def cap_urls(urls: list[str], *, max_count: int = MAX_URLS_LOG) -> list[str]:
    """Cap URL list length for log fields."""
    return list(urls[:max_count])


def tool_types_from_body(body: dict[str, Any]) -> list[str]:
    """Extract tool type strings from request body."""
    tools = body.get("tools")
    if not isinstance(tools, list):
        return []
    return [str(t.get("type")) for t in tools if isinstance(t, dict) and t.get("type")]


def resolve_request_mode(body: dict[str, Any]) -> str:
    """Classify request mode for logging (plain, reasoning, function, web_search)."""
    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and tool.get("type") == "web_search":
                return "web_search"
        for tool in tools:
            if isinstance(tool, dict) and tool.get("type") == "function":
                return "function"
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("enabled"):
        return "reasoning"
    return "plain"


def web_search_invoked(body: dict[str, Any]) -> str:
    """yes | no — whether web_search tool is present."""
    return "yes" if "web_search" in tool_types_from_body(body) else "no"


def get_logger(name: str) -> logging.Logger:
    """Named logger under chat_proxy hierarchy."""
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit a structured log line; request_id is injected when missing."""
    extra = dict(fields)
    extra.setdefault("request_id", get_request_id())
    extra["event"] = event
    logger.log(level, event, extra=extra)


def log_request_start(body: dict[str, Any]) -> None:
    log_event(
        get_logger("chat_proxy.http"),
        "request_start",
        model=body.get("model"),
        stream=bool(body.get("stream")),
        mode=resolve_request_mode(body),
        tool_types=tool_types_from_body(body),
        web_search_invoked=web_search_invoked(body),
    )


def log_request_end(
    *,
    mode: str,
    status: str,
    duration_ms: float,
) -> None:
    log_event(
        get_logger("chat_proxy.http"),
        "request_end",
        mode=mode,
        status=status,
        duration_ms=round(duration_ms, 2),
    )


def log_validation_error(*, code: str, param: str | None) -> None:
    log_event(
        get_logger("chat_proxy.http"),
        "validation_error",
        level=logging.WARNING,
        code=code,
        param=param,
    )


def log_upstream_error(
    *,
    stage: str,
    tool: str | None = None,
    exc: BaseException,
) -> None:
    log_event(
        get_logger("chat_proxy.upstream"),
        "upstream_error",
        level=logging.ERROR,
        stage=stage,
        tool=tool,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )


def log_route_mode(*, mode: str, tool_types: list[str]) -> None:
    log_event(
        get_logger("chat_proxy.routing"),
        "route_mode",
        mode=mode,
        tool_types=tool_types,
    )
