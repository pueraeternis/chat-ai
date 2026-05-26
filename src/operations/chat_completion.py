"""Route chat completion requests by tool/reasoning mode."""

from __future__ import annotations

from typing import Any

from adapters.mcp_tool_client import McpToolClient
from core.errors import ValidationError
from core.ports import InferencePort
from core.settings import ChatProxySettings
from core.system_tool_registry import SYSTEM_TOOL_TYPES, SystemToolBinding, SystemToolRegistry
from operations.reasoning_fallback import normalize_assistant_message


def _tools_list(body: dict[str, Any]) -> list[dict[str, Any]]:
    tools = body.get("tools")
    if tools is None:
        return []
    if not isinstance(tools, list):
        raise ValidationError("tools must be an array", code="invalid_request_error")
    return [t for t in tools if isinstance(t, dict)]


def _function_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tools if t.get("type") == "function"]


def _system_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tools if t.get("type") != "function"]


def _reasoning_enabled(body: dict[str, Any]) -> bool:
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict):
        return bool(reasoning.get("enabled"))
    return False


def _reject_reasoning_in_messages(messages: list[Any]) -> None:
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("reasoning_content") or msg.get("reasoning"):
            raise ValidationError(
                "reasoning fields are not allowed in input messages",
                code="invalid_request_error",
                param="messages",
            )


def _reject_stream(body: dict[str, Any]) -> None:
    if body.get("stream"):
        raise ValidationError(
            "Streaming is not supported in v1",
            code="not_supported",
        )


class ChatCompletionService:
    """Application service for POST /v1/chat/completions."""

    def __init__(
        self,
        inference: InferencePort,
        settings: ChatProxySettings,
        registry: SystemToolRegistry,
    ) -> None:
        self._inference = inference
        self._settings = settings
        self._registry = registry

    def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        _reject_stream(body)
        tools = _tools_list(body)
        messages = body.get("messages")
        if not isinstance(messages, list):
            raise ValidationError("messages is required", param="messages")

        _reject_reasoning_in_messages(messages)

        func_tools = _function_tools(tools)
        sys_tools = _system_tools(tools)
        reasoning_on = _reasoning_enabled(body)

        if func_tools and sys_tools:
            raise ValidationError(
                "Cannot mix system tools and function tools",
                code="conflicting_tools",
            )
        if reasoning_on and tools:
            raise ValidationError(
                "reasoning cannot be used with tools",
                code="conflicting_reasoning",
            )

        if sys_tools:
            return self._handle_system_tool(body, sys_tools)
        if func_tools:
            return self._handle_client_functions(body)
        if reasoning_on:
            return self._handle_reasoning(body)
        return self._handle_plain(body)

    def _handle_plain(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        return self._inference.chat_completion(vllm_body)

    def _handle_client_functions(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        completion = self._inference.chat_completion(vllm_body)
        return _normalize_tool_calls_completion(completion)

    def _handle_reasoning(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        vllm_body["chat_template_kwargs"] = {"enable_thinking": True}
        completion = self._inference.chat_completion(vllm_body)
        return _passthrough_vllm_reasoning_fields(completion)

    def _handle_system_tool(
        self,
        body: dict[str, Any],
        sys_tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(sys_tools) > 1:
            raise ValidationError(
                "Only one system tool per request is supported",
                code="invalid_request_error",
            )
        tool = sys_tools[0]
        tool_type = str(tool.get("type", ""))
        if tool_type not in SYSTEM_TOOL_TYPES:
            raise ValidationError(
                f"Unsupported system tool type: {tool_type}",
                code="invalid_request_error",
            )
        if tool_type == "web_search":
            return self._handle_web_search(body, tool)
        msg = f"Unsupported system tool: {tool_type}"
        raise ValidationError(msg, code="invalid_request_error")

    def _handle_web_search(
        self,
        body: dict[str, Any],
        tool: dict[str, Any],
    ) -> dict[str, Any]:
        user_location = tool.get("user_location")
        if not user_location:
            raise ValidationError(
                "user_location is required for web_search",
                code="missing_required_parameter",
                param="tools[0].user_location",
            )
        messages = body.get("messages")
        if not isinstance(messages, list):
            raise ValidationError("messages is required", param="messages")

        mcp_url = self._registry.mcp_url_for("web_search")
        mcp = McpToolClient(mcp_url, timeout_seconds=self._settings.mcp_timeout_seconds)
        orchestrator = self._registry.create_web_search_orchestrator(
            self._inference,
            mcp,
            default_model=self._settings.default_model,
        )
        return orchestrator.run(
            model=body.get("model"),
            messages=messages,
            web_search_tool=tool,
            user_location=user_location,
        )


def _strip_proxy_fields(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    out.pop("reasoning", None)
    return out


def _normalize_tool_calls_completion(completion: dict[str, Any]) -> dict[str, Any]:
    choices = completion.get("choices")
    if not isinstance(choices, list):
        return completion
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("tool_calls") and message.get("content") is None:
            continue
        if message.get("tool_calls"):
            message["content"] = None
            choice["finish_reason"] = "tool_calls"
    return completion


def _passthrough_vllm_reasoning_fields(completion: dict[str, Any]) -> dict[str, Any]:
    choices = completion.get("choices")
    if not isinstance(choices, list):
        return completion
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            choice["message"] = normalize_assistant_message(message)
    return completion


def build_registry(settings: ChatProxySettings) -> SystemToolRegistry:
    return SystemToolRegistry(
        {
            "web_search": SystemToolBinding(
                tool_type="web_search",
                mcp_url=settings.web_search_mcp_url,
            ),
        },
    )
