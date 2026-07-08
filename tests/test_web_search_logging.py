"""Unit tests for web_search pipeline structured logging."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from adapters.mcp_tool_client import McpToolClient
from core.logging_config import configure_logging
from core.request_context import reset_request_id, set_request_id
from core.settings import ChatProxySettings
from operations.web_search_pipeline import WebSearchOrchestrator

_USER_LOCATION = {"approximate": {"country": "US", "city": "New York"}}


_CHAT_PROXY_LOGGERS = (
    "chat_proxy",
    "chat_proxy.http",
    "chat_proxy.routing",
    "chat_proxy.web_search",
    "chat_proxy.upstream",
)


@pytest.fixture(autouse=True)
def _logging_configured(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging(ChatProxySettings(log_level="INFO", log_json=False))
    for name in _CHAT_PROXY_LOGGERS:
        logging.getLogger(name).addHandler(caplog.handler)


@pytest.fixture
def inference() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mcp() -> MagicMock:
    client = MagicMock(spec=McpToolClient)
    return client


@pytest.fixture
def orchestrator(inference: MagicMock, mcp: MagicMock) -> WebSearchOrchestrator:
    return WebSearchOrchestrator(inference=inference, mcp=mcp, default_model="test-model")


def _run(
    orchestrator: WebSearchOrchestrator,
    inference: MagicMock,
    mcp: MagicMock,
    *,
    router_action: str = "SEARCH",
    hits: list[dict[str, Any]] | None = None,
) -> None:
    inference.chat_completion.side_effect = [
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"action":"'
                            + router_action
                            + '","query":"test query","language":"en"}'
                        ),
                    },
                },
            ],
        },
        {"choices": [{"message": {"content": '{"urls":["https://a.example"]}'}}]},
        {"choices": [{"message": {"content": "final answer"}}]},
    ]
    if hits is None:
        hits = [
            {"url": "https://a.example", "title": "A", "content": "snippet"},
            {"url": "https://b.example", "title": "B", "content": "snippet"},
        ]
    mcp.call_tool_sync.side_effect = [
        {"results": hits},
        {"markdown": "# page\n\ncontent"},
    ]
    token = set_request_id("ws-test-req")
    try:
        orchestrator.run(
            model="test-model",
            messages=[{"role": "user", "content": "hello world"}],
            web_search_tool={
                "type": "web_search",
                "search_context_size": "low",
                "user_location": _USER_LOCATION,
            },
            user_location=_USER_LOCATION,
        )
    finally:
        reset_request_id(token)


def test_web_search_skip_logs(
    caplog: pytest.LogCaptureFixture, orchestrator, inference, mcp
) -> None:
    caplog.set_level(logging.INFO, logger="chat_proxy.web_search")
    _run(orchestrator, inference, mcp, router_action="SKIP", hits=[])
    messages = [r.message for r in caplog.records]
    assert "web_search_start" in messages
    assert "router_result" in messages
    assert "search_hits" not in messages
    complete = next(r for r in caplog.records if r.message == "web_search_complete")
    assert getattr(complete, "outcome", None) == "skip"


def test_web_search_hits_logs(
    caplog: pytest.LogCaptureFixture, orchestrator, inference, mcp
) -> None:
    caplog.set_level(logging.INFO, logger="chat_proxy.web_search")
    _run(orchestrator, inference, mcp)
    messages = [r.message for r in caplog.records]
    assert "search_hits" in messages
    hits = next(r for r in caplog.records if r.message == "search_hits")
    assert getattr(hits, "hit_count", None) == 2
    urls = getattr(hits, "urls", [])
    assert "https://a.example" in urls
    complete = next(r for r in caplog.records if r.message == "web_search_complete")
    assert getattr(complete, "outcome", None) == "success"


def test_web_search_no_hits_logs(
    caplog: pytest.LogCaptureFixture, orchestrator, inference, mcp
) -> None:
    caplog.set_level(logging.INFO, logger="chat_proxy.web_search")
    inference.chat_completion.side_effect = [
        {
            "choices": [
                {
                    "message": {
                        "content": '{"action":"SEARCH","query":"empty","language":"en"}',
                    },
                },
            ],
        },
        {"choices": [{"message": {"content": "fallback answer"}}]},
    ]
    mcp.call_tool_sync.return_value = {"results": []}
    token = set_request_id("ws-no-hits")
    try:
        orchestrator.run(
            model="test-model",
            messages=[{"role": "user", "content": "query"}],
            web_search_tool={
                "type": "web_search",
                "user_location": _USER_LOCATION,
            },
            user_location=_USER_LOCATION,
        )
    finally:
        reset_request_id(token)

    assert "search_no_hits" in [r.message for r in caplog.records]
    complete = next(r for r in caplog.records if r.message == "web_search_complete")
    assert getattr(complete, "outcome", None) == "no_hits"
