"""Map vLLM ``reasoning`` deltas to ``reasoning_content`` in SSE streams."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


async def map_reasoning_sse_stream(source: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Rewrite ``data:`` JSON lines that use ``delta.reasoning`` → ``delta.reasoning_content``."""
    buffer = b""
    async for chunk in source:
        buffer += chunk
        while True:
            sep = buffer.find(b"\n\n")
            if sep < 0:
                break
            event, buffer = buffer[:sep], buffer[sep + 2 :]
            yield _map_event_bytes(event) + b"\n\n"
    if buffer:
        yield _map_event_bytes(buffer)


def _map_event_bytes(event: bytes) -> bytes:
    if not event.strip():
        return event
    lines: list[bytes] = []
    for line in event.split(b"\n"):
        if line.startswith(b"data: "):
            payload = line[6:]
            if payload.strip() == b"[DONE]":
                lines.append(line)
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if isinstance(data, dict):
                _map_reasoning_in_chunk(data)
                lines.append(b"data: " + json.dumps(data, ensure_ascii=False).encode())
                continue
        lines.append(line)
    return b"\n".join(lines)


def _map_reasoning_in_chunk(data: dict) -> None:
    choices = data.get("choices")
    if not isinstance(choices, list):
        return
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue
        reasoning = delta.pop("reasoning", None)
        if reasoning and not delta.get("reasoning_content"):
            delta["reasoning_content"] = reasoning
