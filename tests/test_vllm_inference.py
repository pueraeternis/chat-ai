"""Unit tests for vLLM HTTP error handling."""

from __future__ import annotations

import httpx
import pytest

from adapters.vllm_inference import VllmInferenceAdapter
from core.errors import InferenceError
from core.settings import ChatProxySettings


def _adapter_with_transport(transport: httpx.BaseTransport) -> VllmInferenceAdapter:
    adapter = VllmInferenceAdapter(ChatProxySettings(vllm_base_url="http://test-vllm/v1"))
    adapter._client.close()
    adapter._async_client = httpx.AsyncClient(base_url="http://test-vllm/v1", transport=transport)
    adapter._client = httpx.Client(
        base_url="http://test-vllm/v1",
        transport=transport,
    )
    return adapter


def test_chat_completion_preserves_openai_shaped_upstream_error() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            400,
            json={
                "error": {
                    "message": "model is required",
                    "type": "invalid_request_error",
                    "code": "missing_required_parameter",
                    "param": "model",
                }
            },
        )
    )
    adapter = _adapter_with_transport(transport)

    with pytest.raises(InferenceError) as exc_info:
        adapter.chat_completion({"messages": []})

    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.payload == {
        "error": {
            "message": "model is required",
            "type": "invalid_request_error",
            "code": "missing_required_parameter",
            "param": "model",
        }
    }


def test_chat_completion_uses_safe_fallback_for_non_json_upstream_error() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(502, text="<html>bad gateway</html>")
    )
    adapter = _adapter_with_transport(transport)

    with pytest.raises(InferenceError) as exc_info:
        adapter.chat_completion({"messages": []})

    exc = exc_info.value
    assert exc.status_code == 502
    assert exc.payload is None
    assert exc.message == "Upstream inference request failed"
