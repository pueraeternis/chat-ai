"""Lightweight request-contract validation for chat completions."""

from __future__ import annotations

from typing import Any

from core.errors import ValidationError

_SUPPORTED_MESSAGE_ROLES = {"system", "user", "assistant", "tool", "developer", "function"}


def validate_chat_completion_request(body: dict[str, Any]) -> None:
    """Validate fields the proxy depends on for routing and compatibility."""
    _validate_model(body.get("model"))
    _validate_messages(body)
    _validate_stream(body)
    _validate_tools(body.get("tools"))


def _validate_model(model: Any) -> None:
    if model is None:
        return
    if not isinstance(model, str) or not model.strip():
        raise ValidationError(
            "model must be a non-empty string",
            param="model",
        )


def _validate_messages(body: dict[str, Any]) -> None:
    if "messages" not in body or not isinstance(body.get("messages"), list):
        raise ValidationError(
            "messages is required and must be an array",
            param="messages",
        )
    messages = body["messages"]
    for index, message in enumerate(messages):
        param = f"messages[{index}]"
        if not isinstance(message, dict):
            raise ValidationError(
                "each message must be an object",
                param=param,
            )
        _validate_message_role(message.get("role"), param=f"{param}.role")
        _validate_message_content(message, param=f"{param}.content")


def _validate_message_role(role: Any, *, param: str) -> None:
    if not isinstance(role, str) or role not in _SUPPORTED_MESSAGE_ROLES:
        supported = ", ".join(sorted(_SUPPORTED_MESSAGE_ROLES))
        raise ValidationError(
            f"message role must be one of: {supported}",
            param=param,
        )


def _validate_message_content(message: dict[str, Any], *, param: str) -> None:
    role = message.get("role")
    if "content" not in message:
        if role == "assistant" and (message.get("tool_calls") or message.get("function_call")):
            return
        raise ValidationError("message content is required", param=param)

    content = message["content"]
    if content is None or isinstance(content, str):
        return
    if isinstance(content, list):
        for index, part in enumerate(content):
            if not isinstance(part, dict):
                raise ValidationError(
                    "message content parts must be objects",
                    param=f"{param}[{index}]",
                )
        return
    raise ValidationError(
        "message content must be a string, null, or an array of content parts",
        param=param,
    )


def _validate_stream(body: dict[str, Any]) -> None:
    stream = body.get("stream")
    if stream is not None and not isinstance(stream, bool):
        raise ValidationError("stream must be a boolean", param="stream")


def _validate_tools(tools: Any) -> None:
    if tools is None:
        return
    if not isinstance(tools, list):
        raise ValidationError("tools must be an array", param="tools")
    for index, tool in enumerate(tools):
        param = f"tools[{index}]"
        if not isinstance(tool, dict):
            raise ValidationError("each tool must be an object", param=param)
        tool_type = tool.get("type")
        if not isinstance(tool_type, str) or not tool_type.strip():
            raise ValidationError("tool type must be a non-empty string", param=f"{param}.type")
        if tool_type != "function":
            continue
        function = tool.get("function")
        if not isinstance(function, dict):
            raise ValidationError(
                "function tool must include a function object",
                param=f"{param}.function",
            )
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(
                "function.name must be a non-empty string",
                param=f"{param}.function.name",
            )
        parameters = function.get("parameters")
        if parameters is not None and not isinstance(parameters, dict):
            raise ValidationError(
                "function.parameters must be an object",
                param=f"{param}.function.parameters",
            )
