"""Unit tests for synthetic web-search chat completion responses."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from adapters.mcp_tool_client import McpToolClient
from operations.web_search_pipeline import WebSearchOrchestrator


def _orchestrator() -> WebSearchOrchestrator:
    return WebSearchOrchestrator(
        inference=MagicMock(),
        mcp=MagicMock(spec=McpToolClient),
        default_model="test-model",
    )


def test_build_response_generates_unique_openai_like_metadata() -> None:
    orchestrator = _orchestrator()
    before = int(time.time())
    first = orchestrator._build_response("test-model", "answer", [])
    second = orchestrator._build_response("test-model", "answer", [])
    after = int(time.time())

    assert first["id"].startswith("chatcmpl-")
    assert second["id"].startswith("chatcmpl-")
    assert first["id"] != second["id"]
    assert before <= first["created"] <= after
    assert first["object"] == "chat.completion"
    assert first["usage"] is None
    assert first["choices"][0]["index"] == 0
    assert first["choices"][0]["finish_reason"] == "stop"
    assert first["choices"][0]["message"] == {"role": "assistant", "content": "answer"}


def test_build_response_includes_annotations_only_when_present() -> None:
    orchestrator = _orchestrator()
    response = orchestrator._build_response(
        "test-model",
        "answer",
        [
            {
                "type": "url_citation",
                "url_citation": {"url": "https://example.com", "title": "Example"},
            }
        ],
    )

    assert response["choices"][0]["message"]["role"] == "assistant"
    assert response["choices"][0]["message"]["content"] == "answer"
    assert response["choices"][0]["message"]["annotations"][0]["type"] == "url_citation"
