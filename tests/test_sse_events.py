"""Unit tests for OWUI SSE event formatting."""

from __future__ import annotations

import json

from operations.sse_events import owui_citation_event, owui_status_event, sse_data_line


def test_status_event_shape() -> None:
    raw = owui_status_event("Searching the web…", done=False, action="web_search")
    assert raw.startswith(b"data: ")
    payload = json.loads(raw.removeprefix(b"data: ").strip())
    assert payload["event"]["type"] == "status"
    data = payload["event"]["data"]
    assert data["description"] == "Searching the web…"
    assert data["done"] is False
    assert data["action"] == "web_search"


def test_citation_event_shape() -> None:
    raw = owui_citation_event(url="https://example.com", title="Example", excerpt="snippet")
    payload = json.loads(raw.removeprefix(b"data: ").strip())
    assert payload["event"]["type"] == "citation"
    cite = payload["event"]["data"]
    assert cite["source"]["url"] == "https://example.com"
    assert cite["metadata"][0]["source"] == "Example"


def test_sse_data_line_ends_with_blank_line() -> None:
    line = sse_data_line({"hello": "world"})
    assert line.endswith(b"\n\n")
