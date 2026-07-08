"""vLLM OpenAI-compatible HTTP adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.errors import InferenceError
from core.log_events import log_upstream_error
from core.openai_errors import openai_error_payload
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
            raise _build_inference_error(exc, fallback_message="Upstream inference request failed") from exc
        return resp.json()

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post("/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log_upstream_error(stage="vllm", tool=None, exc=exc)
            raise _build_inference_error(exc, fallback_message="Upstream inference request failed") from exc
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
            raise _build_inference_error(exc, fallback_message="Upstream inference request failed") from exc


def _build_inference_error(exc: httpx.HTTPError, *, fallback_message: str) -> InferenceError:
    payload: dict[str, Any] | None = None
    status_code = 502
    response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
    if response is not None:
        status_code = response.status_code
        payload = _safe_openai_error_payload(response)
    if payload is not None:
        return InferenceError(
            payload["error"]["message"],
            code=str(payload["error"].get("code") or "inference_error"),
            status_code=status_code,
            payload=payload,
        )
    return InferenceError(fallback_message, status_code=502)


def _safe_openai_error_payload(response: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None

    message = error.get("message")
    error_type = error.get("type")
    if not isinstance(message, str) or not message.strip():
        return None
    if not isinstance(error_type, str) or not error_type.strip():
        return None

    safe_payload = openai_error_payload(
        message,
        error_type=error_type,
        code=_safe_scalar_string(error.get("code"), default="inference_error") or "inference_error",
        param=_safe_scalar_string(error.get("param")),
    )
    return safe_payload


def _safe_scalar_string(value: Any, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return default
