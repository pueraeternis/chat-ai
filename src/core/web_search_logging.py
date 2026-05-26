"""web_search pipeline log events."""

from __future__ import annotations

import logging
from typing import Any

from core.log_events import cap_urls, get_logger, log_event, truncate_query

_WS_LOGGER = get_logger("chat_proxy.web_search")


def log_web_search_start(
    *,
    search_context_size: str,
    searxng_language: str,
    budget_max_urls: int,
) -> None:
    log_event(
        _WS_LOGGER,
        "web_search_start",
        search_context_size=search_context_size,
        searxng_language=searxng_language,
        budget_max_urls=budget_max_urls,
    )


def log_router_result(router: dict[str, Any]) -> None:
    query = str(router.get("query") or "")
    log_event(
        _WS_LOGGER,
        "router_result",
        action=router.get("action"),
        query=truncate_query(query),
        language=router.get("language"),
    )


def log_search_hits(*, query: str, hits: list[dict[str, Any]]) -> None:
    urls = cap_urls([str(h["url"]) for h in hits if h.get("url")])
    log_event(
        _WS_LOGGER,
        "search_hits",
        query=truncate_query(query),
        hit_count=len(hits),
        urls=urls,
    )


def log_search_no_hits(*, query: str) -> None:
    log_event(
        _WS_LOGGER,
        "search_no_hits",
        query=truncate_query(query),
    )


def log_url_filter_result(*, selected_urls: list[str], fallback_used: bool) -> None:
    log_event(
        _WS_LOGGER,
        "url_filter_result",
        selected_urls=cap_urls(selected_urls),
        fallback_used=fallback_used,
    )


def log_fetch_results(
    *,
    requested_urls: list[str],
    fetched_urls: list[str],
    failed_urls: list[str],
) -> None:
    log_event(
        _WS_LOGGER,
        "fetch_results",
        requested_urls=cap_urls(requested_urls),
        fetched_urls=cap_urls(fetched_urls),
        failed_urls=cap_urls(failed_urls),
    )


def log_web_search_complete(
    *,
    outcome: str,
    pages_fetched: int,
    duration_ms: float,
    level: int = logging.INFO,
) -> None:
    log_event(
        _WS_LOGGER,
        "web_search_complete",
        level=level,
        outcome=outcome,
        pages_fetched=pages_fetched,
        duration_ms=round(duration_ms, 2),
    )
