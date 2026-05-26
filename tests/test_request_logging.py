"""Unit tests for request mode resolution and request log events."""

from __future__ import annotations

import logging

import pytest

from core.log_events import log_request_start, resolve_request_mode, tool_types_from_body
from core.logging_config import configure_logging
from core.request_context import reset_request_id, set_request_id
from core.settings import ChatProxySettings


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


def test_resolve_request_mode_plain() -> None:
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert resolve_request_mode(body) == "plain"
    assert tool_types_from_body(body) == []


def test_resolve_request_mode_web_search() -> None:
    body = {
        "messages": [{"role": "user", "content": "news"}],
        "tools": [
            {
                "type": "web_search",
                "user_location": {"approximate": {"country": "RU"}},
            },
        ],
    }
    assert resolve_request_mode(body) == "web_search"
    assert tool_types_from_body(body) == ["web_search"]


def test_log_request_start_plain(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="chat_proxy.http")
    token = set_request_id("test-req-plain")
    try:
        log_request_start({"messages": [{"role": "user", "content": "hi"}], "stream": False})
    finally:
        reset_request_id(token)

    assert any("request_start" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if r.message == "request_start")
    assert getattr(record, "mode", None) == "plain"
    assert getattr(record, "web_search_invoked", None) == "no"
    assert getattr(record, "request_id", None) == "test-req-plain"


def test_log_request_start_web_search(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="chat_proxy.http")
    body = {
        "model": "qwen3-vl-30b-instruct",
        "stream": True,
        "messages": [{"role": "user", "content": "weather"}],
        "tools": [
            {
                "type": "web_search",
                "user_location": {"approximate": {"country": "US"}},
            },
        ],
    }
    token = set_request_id("test-req-ws")
    try:
        log_request_start(body)
    finally:
        reset_request_id(token)

    record = next(r for r in caplog.records if r.message == "request_start")
    assert getattr(record, "mode", None) == "web_search"
    assert getattr(record, "web_search_invoked", None) == "yes"
    assert getattr(record, "stream", None) is True
