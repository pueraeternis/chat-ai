"""HTTP contract regression tests for chat completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.http_api import create_app
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry


class _RecordingInference:
    def __init__(self) -> None:
        self.chat_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    def list_models(self) -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "test-model"}]}

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        self.chat_calls.append(body)
        return {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }

    async def chat_completion_stream(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        self.stream_calls.append(body)
        yield b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    def close(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


@pytest.fixture
def app() -> Any:
    application = create_app()
    settings = ChatProxySettings()
    inference = _RecordingInference()
    application.state.settings = settings
    application.state.inference = inference
    application.state.chat_service = ChatCompletionService(
        inference,  # type: ignore[arg-type]
        settings,
        build_registry(settings),
    )
    return application


@pytest.fixture
def inference(app) -> _RecordingInference:
    return app.state.inference


@pytest.mark.asyncio
async def test_malformed_json_returns_openai_error(app, inference: _RecordingInference) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            content=b'{"messages": [}',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "message": "Malformed JSON request body",
            "type": "invalid_request_error",
            "code": "invalid_request_error",
        }
    }
    assert inference.chat_calls == []
    assert inference.stream_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_kwargs", "expected_message"),
    [
        ({"json": [1, 2]}, "Request body must be a JSON object"),
        ({"json": "hello"}, "Request body must be a JSON object"),
        (
            {"content": b"null", "headers": {"Content-Type": "application/json"}},
            "Request body must be a JSON object",
        ),
    ],
)
async def test_non_object_json_returns_openai_error(
    app,
    inference: _RecordingInference,
    request_kwargs: dict[str, Any],
    expected_message: str,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", **request_kwargs)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["message"] == expected_message
    assert body["error"]["type"] == "invalid_request_error"
    assert inference.chat_calls == []
    assert inference.stream_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "message", "param"),
    [
        ({}, "messages is required and must be an array", "messages"),
        ({"messages": "hi"}, "messages is required and must be an array", "messages"),
        (
            {"messages": ["hi"]},
            "each message must be an object",
            "messages[0]",
        ),
        (
            {"messages": [{"role": "user", "content": "hi"}], "model": ""},
            "model must be a non-empty string",
            "model",
        ),
        (
            {"messages": [{"role": "user", "content": "hi"}], "stream": "false"},
            "stream must be a boolean",
            "stream",
        ),
        (
            {"messages": [{"role": "user", "content": "hi"}], "tools": {}},
            "tools must be an array",
            "tools",
        ),
        (
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": ""}}],
            },
            "function.name must be a non-empty string",
            "tools[0].function.name",
        ),
    ],
)
async def test_invalid_request_shape_returns_validation_error(
    app,
    inference: _RecordingInference,
    payload: dict[str, Any],
    message: str,
    param: str,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["message"] == message
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["param"] == param
    assert inference.chat_calls == []
    assert inference.stream_calls == []


@pytest.mark.asyncio
async def test_unknown_fields_pass_through_to_inference(
    app, inference: _RecordingInference
) -> None:
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
        "parallel_tool_calls": False,
        "stream_options": {"include_usage": True},
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert inference.chat_calls == [payload]


@pytest.mark.asyncio
async def test_invalid_stream_value_does_not_enter_sse_branch(
    app, inference: _RecordingInference
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": "false"},
        )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert inference.stream_calls == []


@pytest.mark.asyncio
async def test_missing_messages_with_stream_true_returns_json_400_before_sse(
    app, inference: _RecordingInference
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json={"stream": True})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["param"] == "messages"
    assert inference.stream_calls == []


@pytest.mark.asyncio
async def test_sdk_style_assistant_tool_call_messages_pass_through(
    app, inference: _RecordingInference
) -> None:
    payload = {
        "model": "test-model",
        "messages": [
            {"role": "user", "content": "What's the weather?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city":"Kyiv"}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "content": '{"temperature":21}',
            },
        ],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert inference.chat_calls == [payload]


@pytest.mark.asyncio
async def test_developer_and_function_roles_pass_through(
    app, inference: _RecordingInference
) -> None:
    payload = {
        "model": "test-model",
        "messages": [
            {"role": "developer", "content": "Prefer concise answers."},
            {"role": "user", "content": "Call the legacy function."},
            {
                "role": "assistant",
                "content": None,
                "function_call": {"name": "legacy_lookup", "arguments": "{}"},
            },
            {"role": "function", "name": "legacy_lookup", "content": '{"ok":true}'},
        ],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert inference.chat_calls == [payload]


@pytest.mark.asyncio
async def test_stream_web_search_missing_user_location_returns_json_400_before_sse(
    app,
    inference: _RecordingInference,
) -> None:
    payload = {
        "messages": [{"role": "user", "content": "news"}],
        "stream": True,
        "tools": [{"type": "web_search"}],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["param"] == "tools[0].user_location"
    assert inference.stream_calls == []


@pytest.mark.asyncio
async def test_stream_unsupported_system_tool_returns_json_400_before_sse(
    app,
    inference: _RecordingInference,
) -> None:
    payload = {
        "messages": [{"role": "user", "content": "find files"}],
        "stream": True,
        "tools": [{"type": "file_search"}],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["param"] == "tools[0].type"
    assert inference.stream_calls == []


@pytest.mark.asyncio
async def test_stream_multiple_system_tools_returns_json_400_before_sse(
    app,
    inference: _RecordingInference,
) -> None:
    payload = {
        "messages": [{"role": "user", "content": "news"}],
        "stream": True,
        "tools": [
            {
                "type": "web_search",
                "user_location": {"approximate": {"country": "US"}},
            },
            {
                "type": "web_search",
                "user_location": {"approximate": {"country": "US"}},
            },
        ],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["param"] == "tools"
    assert inference.stream_calls == []
