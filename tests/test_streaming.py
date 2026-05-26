"""Unit tests for SSE streaming routing and passthrough."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry
from operations.sse_events import owui_status_event
from operations.stream_passthrough import passthrough_vllm_stream
from operations.stream_reasoning import map_reasoning_sse_stream


class FakeInference:
    def __init__(self, stream_chunks: list[bytes] | None = None) -> None:
        self._stream_chunks = stream_chunks or [
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        self.last_stream_body: dict[str, Any] | None = None

    def list_models(self) -> dict[str, Any]:
        return {"data": []}

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "ok"}}]}

    async def chat_completion_stream(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        self.last_stream_body = body
        for chunk in self._stream_chunks:
            yield chunk


@pytest.fixture
def inference() -> FakeInference:
    return FakeInference()


@pytest.fixture
def service(inference: FakeInference) -> ChatCompletionService:
    settings = ChatProxySettings()
    return ChatCompletionService(inference, settings, build_registry(settings))


async def _collect_stream(service: ChatCompletionService, body: dict[str, Any]) -> bytes:
    parts: list[bytes] = []
    async for chunk in service.stream(body):
        parts.append(chunk)
    return b"".join(parts)


@pytest.mark.asyncio
async def test_plain_stream_sets_stream_true(
    service: ChatCompletionService,
    inference: FakeInference,
) -> None:
    out = await _collect_stream(
        service,
        {"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert b"data: [DONE]" in out
    assert inference.last_stream_body is not None
    assert inference.last_stream_body.get("stream") is True
    assert "reasoning" not in inference.last_stream_body


@pytest.mark.asyncio
async def test_reasoning_stream_enables_thinking(
    service: ChatCompletionService,
    inference: FakeInference,
) -> None:
    await _collect_stream(
        service,
        {
            "messages": [{"role": "user", "content": "think"}],
            "stream": True,
            "reasoning": {"enabled": True},
        },
    )
    assert inference.last_stream_body is not None
    assert inference.last_stream_body.get("chat_template_kwargs") == {
        "enable_thinking": True,
    }


@pytest.mark.asyncio
async def test_map_reasoning_sse_renames_delta_field() -> None:
    async def source() -> AsyncIterator[bytes]:
        yield (b'data: {"choices":[{"delta":{"reasoning":"thought"}}]}\n\ndata: [DONE]\n\n')

    out = b""
    async for chunk in map_reasoning_sse_stream(source()):
        out += chunk
    payload = json.loads(out.split(b"data: ")[1].split(b"\n\n")[0])
    assert payload["choices"][0]["delta"]["reasoning_content"] == "thought"
    assert "reasoning" not in payload["choices"][0]["delta"]


@pytest.mark.asyncio
async def test_passthrough_injects_annotations_before_done(inference: FakeInference) -> None:
    out = b""
    async for chunk in passthrough_vllm_stream(
        inference,
        {"model": "m", "messages": []},
        annotations=[
            {
                "type": "url_citation",
                "url_citation": {"url": "https://x", "title": "X"},
            },
        ],
    ):
        out += chunk
    assert b'"annotations"' in out
    assert out.index(b'"annotations"') < out.index(b"[DONE]")


@pytest.mark.asyncio
async def test_web_search_stream_emits_status_events(
    service: ChatCompletionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubOrchestrator:
        async def run_stream(self, **_kwargs: Any) -> AsyncIterator[bytes]:
            yield owui_status_event("Searching the web…", done=False)
            yield b"data: [DONE]\n\n"

    stub = StubOrchestrator()

    def orchestrator_stub() -> StubOrchestrator:
        return stub

    monkeypatch.setattr(service, "_web_search_orchestrator", orchestrator_stub)

    out = await _collect_stream(
        service,
        {
            "messages": [{"role": "user", "content": "news"}],
            "stream": True,
            "tools": [
                {
                    "type": "web_search",
                    "user_location": {"approximate": {"country": "US"}},
                },
            ],
        },
    )
    assert b'"type": "status"' in out or b'"type":"status"' in out
