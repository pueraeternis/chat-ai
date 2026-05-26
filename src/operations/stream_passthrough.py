"""Passthrough vLLM SSE streams with optional annotation injection."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from core.ports import InferencePort
from operations.sse_events import annotations_stream_chunk, sse_done
from operations.stream_reasoning import map_reasoning_sse_stream


async def passthrough_vllm_stream(
    inference: InferencePort,
    body: dict[str, Any],
    *,
    annotations: list[dict[str, Any]] | None = None,
    map_reasoning: bool = False,
) -> AsyncIterator[bytes]:
    """Forward vLLM SSE; optionally inject annotations before ``[DONE]``."""
    stream_body = {**body, "stream": True}
    source = inference.chat_completion_stream(stream_body)
    if map_reasoning:
        source = map_reasoning_sse_stream(source)
    if annotations:
        async for chunk in _inject_annotations_before_done(
            source,
            annotations,
            model=str(body.get("model") or ""),
        ):
            yield chunk
        return
    async for chunk in source:
        yield chunk


async def _inject_annotations_before_done(
    source: AsyncIterator[bytes],
    annotations: list[dict[str, Any]],
    *,
    model: str,
) -> AsyncIterator[bytes]:
    buffer = b""
    async for chunk in source:
        buffer += chunk
        while True:
            sep = buffer.find(b"\n\n")
            if sep < 0:
                break
            event, buffer = buffer[:sep], buffer[sep + 2 :]
            if _is_done_event(event):
                if annotations:
                    yield annotations_stream_chunk(model=model, annotations=annotations)
                yield event + b"\n\n"
            else:
                yield event + b"\n\n"
    if buffer.strip():
        if _is_done_event(buffer):
            if annotations:
                yield annotations_stream_chunk(model=model, annotations=annotations)
            yield buffer if buffer.endswith(b"\n\n") else buffer + b"\n\n"
        else:
            yield buffer if buffer.endswith(b"\n\n") else buffer + b"\n\n"
    elif annotations:
        yield annotations_stream_chunk(model=model, annotations=annotations)
        yield sse_done()


def _is_done_event(event: bytes) -> bool:
    return any(line.strip() == b"data: [DONE]" for line in event.split(b"\n"))
