"""Unit tests for chat-proxy request validation and routing."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from core.errors import ValidationError
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry


@pytest.fixture
def inference() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(inference: MagicMock) -> ChatCompletionService:
    settings = ChatProxySettings()
    return ChatCompletionService(inference, settings, build_registry(settings))


def test_handle_rejects_stream_flag(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match="SSE"):
        service.handle({"messages": [], "stream": True})


def test_handle_rejects_non_boolean_stream(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match="boolean"):
        service.handle({"messages": [], "stream": "false"})


def test_handle_rejects_invalid_model(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match="model must be a non-empty string"):
        service.handle({"model": "", "messages": []})


def test_handle_rejects_unknown_message_role(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match="message role must be one of"):
        service.handle({"messages": [{"role": "bogus", "content": "hi"}]})


def test_handle_allows_assistant_tool_calls_without_content(
    service: ChatCompletionService,
    inference: MagicMock,
) -> None:
    expected: dict[str, Any] = {"choices": [{"message": {"content": "ok"}}]}
    inference.chat_completion.return_value = expected
    out = service.handle(
        {
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": '{"ok":true}'},
            ]
        }
    )
    assert out == expected


def test_handle_allows_developer_and_function_roles(
    service: ChatCompletionService,
    inference: MagicMock,
) -> None:
    expected: dict[str, Any] = {"choices": [{"message": {"content": "ok"}}]}
    inference.chat_completion.return_value = expected
    out = service.handle(
        {
            "messages": [
                {"role": "developer", "content": "be concise"},
                {"role": "user", "content": "legacy"},
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {"name": "lookup", "arguments": "{}"},
                },
                {"role": "function", "name": "lookup", "content": '{"ok":true}'},
            ]
        }
    )
    assert out == expected


def test_handle_rejects_non_object_tool(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match="each tool must be an object"):
        service.handle({"messages": [], "tools": ["web_search"]})


def test_handle_rejects_invalid_function_tool_shape(service: ChatCompletionService) -> None:
    with pytest.raises(ValidationError, match=r"function\.name must be a non-empty string"):
        service.handle(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": ""}}],
            }
        )


def test_conflicting_tools(service: ChatCompletionService) -> None:
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {"type": "web_search", "user_location": {"approximate": {"country": "US"}}},
            {"type": "function", "function": {"name": "x", "parameters": {}}},
        ],
    }
    with pytest.raises(ValidationError, match="mix"):
        service.handle(body)


def test_conflicting_reasoning(service: ChatCompletionService) -> None:
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning": {"enabled": True},
        "tools": [{"type": "function", "function": {"name": "x", "parameters": {}}}],
    }
    with pytest.raises(ValidationError, match="reasoning"):
        service.handle(body)


def test_web_search_missing_user_location(service: ChatCompletionService) -> None:
    body = {
        "messages": [{"role": "user", "content": "news"}],
        "tools": [{"type": "web_search"}],
    }
    with pytest.raises(ValidationError, match="user_location"):
        service.handle(body)


def test_plain_passthrough(
    service: ChatCompletionService,
    inference: MagicMock,
) -> None:
    expected: dict[str, Any] = {"choices": [{"message": {"content": "ok"}}]}
    inference.chat_completion.return_value = expected
    out = service.handle({"messages": [{"role": "user", "content": "hi"}]})
    assert out == expected
    call_body = inference.chat_completion.call_args[0][0]
    assert "reasoning" not in call_body


def test_reasoning_sets_template_kwargs(
    service: ChatCompletionService,
    inference: MagicMock,
) -> None:
    inference.chat_completion.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "answer"}}],
    }
    service.handle(
        {
            "messages": [{"role": "user", "content": "think"}],
            "reasoning": {"enabled": True},
        },
    )
    body = inference.chat_completion.call_args[0][0]
    assert body.get("chat_template_kwargs") == {"enable_thinking": True}
