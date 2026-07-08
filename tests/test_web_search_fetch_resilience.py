"""web_search pipeline tolerates per-URL fetch failures."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from adapters.mcp_tool_client import McpToolClient
from core.errors import McpToolError
from operations.web_search_pipeline import WebSearchOrchestrator


@pytest.fixture
def orchestrator() -> WebSearchOrchestrator:
    return WebSearchOrchestrator(
        inference=MagicMock(),
        mcp=MagicMock(spec=McpToolClient),
        default_model="test-model",
    )


def test_fetch_pages_continues_when_one_url_fails(orchestrator: WebSearchOrchestrator) -> None:
    mcp = cast(MagicMock, orchestrator._mcp)

    def fetch_side_effect(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments["url"] == "https://bad.example/":
            raise McpToolError("FETCH_INTERNAL_ERROR: navigation failed")
        return {"markdown": "# OK\n\ncontent"}

    mcp.call_tool_sync.side_effect = fetch_side_effect

    pages = orchestrator._fetch_pages(
        ["https://bad.example/", "https://good.example/"],
        markdown_max_chars=10_000,
    )

    assert len(pages) == 1
    assert pages[0]["url"] == "https://good.example/"
