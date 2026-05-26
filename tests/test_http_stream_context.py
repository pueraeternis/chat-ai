"""Regression: stream cleanup must reset request_id in the stream task context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.http_api import create_app
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry


class _StreamInference:
    async def chat_completion_stream(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        yield b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    def list_models(self) -> dict[str, Any]:
        return {"data": []}

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "ok"}}]}

    def close(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


@pytest.fixture
def app():
    application = create_app()
    settings = ChatProxySettings()
    inference = _StreamInference()
    application.state.settings = settings
    application.state.inference = inference
    application.state.chat_service = ChatCompletionService(
        inference,  # type: ignore[arg-type]
        settings,
        build_registry(settings),
    )
    return application


@pytest.mark.asyncio
async def test_stream_completes_without_context_reset_error(app) -> None:
    """Consuming the full SSE body must not raise ValueError on contextvar reset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "qwen3-vl-30b-instruct",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        ) as response:
            assert response.status_code == 200
            body = b"".join([chunk async for chunk in response.aiter_bytes()])
    assert b"data: [DONE]" in body
