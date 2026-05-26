"""vLLM OpenAI-compatible HTTP adapter."""

from __future__ import annotations

from typing import Any

import httpx

from core.errors import InferenceError
from core.ports import InferencePort
from core.settings import ChatProxySettings


class VllmInferenceAdapter(InferencePort):
    """Sync HTTP client to vLLM /v1 endpoints."""

    def __init__(self, settings: ChatProxySettings) -> None:
        self._base = settings.vllm_base_url.rstrip("/")
        self._timeout = settings.vllm_timeout_seconds
        self._client = httpx.Client(
            base_url=self._base,
            timeout=httpx.Timeout(self._timeout),
        )

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> dict[str, Any]:
        try:
            resp = self._client.get("/models")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise InferenceError(f"vLLM models request failed: {exc}") from exc
        return resp.json()

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post("/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise InferenceError(f"vLLM chat completion failed: {exc}") from exc
        return resp.json()
