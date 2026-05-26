"""Open WebUI-compatible SSE event lines for orchestrated streams."""

from __future__ import annotations

import json
from typing import Any


def sse_data_line(payload: dict[str, Any]) -> bytes:
    """Format one OpenAI-style SSE ``data:`` line (includes trailing blank line)."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def sse_done() -> bytes:
    return b"data: [DONE]\n\n"


def owui_status_event(
    description: str,
    *,
    done: bool = False,
    action: str | None = "web_search",
    hidden: bool = False,
) -> bytes:
    data: dict[str, Any] = {
        "description": description,
        "done": done,
        "hidden": hidden,
    }
    if action is not None:
        data["action"] = action
    return sse_data_line({"event": {"type": "status", "data": data}})


def owui_citation_event(
    *,
    url: str,
    title: str,
    excerpt: str | None = None,
) -> bytes:
    doc_text = excerpt or title
    metadata = {"source": title, "url": url}
    return sse_data_line(
        {
            "event": {
                "type": "citation",
                "data": {
                    "document": [doc_text],
                    "metadata": [metadata],
                    "source": {"name": title, "url": url},
                },
            },
        },
    )


def url_citation_annotations(pages: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "url_citation",
            "url_citation": {
                "url": p["url"],
                "title": p.get("title") or p["url"],
                "start_index": 0,
                "end_index": 0,
            },
        }
        for p in pages
    ]


def annotations_stream_chunk(
    *,
    model: str,
    annotations: list[dict[str, Any]],
    chunk_id: str = "chatcmpl-websearch",
) -> bytes:
    """Emit a final chunk carrying ``annotations`` for OpenAI SDK stream clients."""
    return sse_data_line(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "annotations": annotations},
                    "finish_reason": None,
                },
            ],
        },
    )
