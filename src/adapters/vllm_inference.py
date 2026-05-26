"""vLLM OpenAI-compatible HTTP adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.errors import InferenceError
from core.log_events import log_upstream_error
from core.ports import InferencePort
from core.settings import ChatProxySettings


class VllmInferenceAdapter(InferencePort):
    """HTTP client to vLLM /v1 endpoints (sync JSON + async SSE stream)."""

    def __init__(self, settings: ChatProxySettings) -> None:
        self._base = settings.vllm_base_url.rstrip("/")
        read_timeout = settings.vllm_timeout_seconds
        connect_timeout = settings.vllm_connect_timeout_seconds
        timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
        self._client = httpx.Client(base_url=self._base, timeout=timeout)
        self._async_client = httpx.AsyncClient(base_url=self._base, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    async def aclose(self) -> None:
        await self._async_client.aclose()

    def list_models(self) -> dict[str, Any]:
        try:
            resp = self._client.get("/models")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log_upstream_error(stage="vllm", tool=None, exc=exc)
            raise InferenceError(f"vLLM models request failed: {exc}") from exc
        return resp.json()

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post("/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log_upstream_error(stage="vllm", tool=None, exc=exc)
            raise InferenceError(f"vLLM chat completion failed: {exc}") from exc
        return resp.json()

    async def chat_completion_stream(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        try:
            async with self._async_client.stream(
                "POST",
                "/chat/completions",
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as exc:
            log_upstream_error(stage="vllm", tool=None, exc=exc)
            raise InferenceError(f"vLLM chat completion stream failed: {exc}") from exc
