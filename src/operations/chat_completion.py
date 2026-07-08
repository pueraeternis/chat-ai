"""Route chat completion requests by tool/reasoning mode."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from adapters.mcp_tool_client import McpToolClient
from core.chat_completion_contract import validate_chat_completion_request
from core.errors import ValidationError
from core.log_events import log_route_mode, resolve_request_mode, tool_types_from_body
from core.ports import InferencePort
from core.settings import ChatProxySettings
from core.system_tool_registry import SYSTEM_TOOL_TYPES, SystemToolBinding, SystemToolRegistry
from operations.reasoning_fallback import normalize_assistant_message
from operations.stream_passthrough import passthrough_vllm_stream


def _tools_list(body: dict[str, Any]) -> list[dict[str, Any]]:
    tools = body.get("tools")
    if tools is None:
        return []
    return tools


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


def _validate_request(body: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Any]]:
    validate_chat_completion_request(body)
    tools = _tools_list(body)
    messages_value = body.get("messages")
    if not isinstance(messages_value, list):
        raise ValidationError("messages is required and must be an array", param="messages")
    messages = messages_value

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
    _validate_system_tools(sys_tools)

    return tools, messages


def _validate_system_tools(sys_tools: list[dict[str, Any]]) -> None:
    if not sys_tools:
        return
    if len(sys_tools) > 1:
        raise ValidationError(
            "Only one system tool per request is supported",
            code="invalid_request_error",
            param="tools",
        )
    tool = sys_tools[0]
    tool_type = str(tool.get("type", ""))
    if tool_type not in SYSTEM_TOOL_TYPES:
        raise ValidationError(
            f"Unsupported system tool type: {tool_type}",
            code="invalid_request_error",
            param="tools[0].type",
        )
    if tool_type == "web_search" and not tool.get("user_location"):
        raise ValidationError(
            "user_location is required for web_search",
            code="missing_required_parameter",
            param="tools[0].user_location",
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

    def validate(self, body: dict[str, Any]) -> None:
        _validate_request(body)

    def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("stream") is True:
            raise ValidationError(
                "stream must use SSE response; set stream false for JSON",
                code="invalid_request_error",
                param="stream",
            )
        tools, messages = _validate_request(body)
        return self._dispatch_json(body, tools, messages)

    async def stream(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        if body.get("stream") is not True:
            raise ValidationError(
                "stream: true is required for streaming",
                code="invalid_request_error",
                param="stream",
            )
        tools, messages = _validate_request(body)
        async for chunk in self._dispatch_stream(body, tools, messages):
            yield chunk

    def _dispatch_json(
        self,
        body: dict[str, Any],
        tools: list[dict[str, Any]],
        messages: list[Any],
    ) -> dict[str, Any]:
        self._log_dispatch(body)
        func_tools = _function_tools(tools)
        sys_tools = _system_tools(tools)
        reasoning_on = _reasoning_enabled(body)

        if sys_tools:
            return self._handle_system_tool(body, sys_tools)
        if func_tools:
            return self._handle_client_functions(body)
        if reasoning_on:
            return self._handle_reasoning(body)
        return self._handle_plain(body)

    async def _dispatch_stream(
        self,
        body: dict[str, Any],
        tools: list[dict[str, Any]],
        messages: list[Any],
    ) -> AsyncIterator[bytes]:
        self._log_dispatch(body)
        func_tools = _function_tools(tools)
        sys_tools = _system_tools(tools)
        reasoning_on = _reasoning_enabled(body)

        if sys_tools:
            async for chunk in self._stream_system_tool(body, sys_tools):
                yield chunk
            return
        if func_tools:
            async for chunk in self._stream_client_functions(body):
                yield chunk
            return
        if reasoning_on:
            async for chunk in self._stream_reasoning(body):
                yield chunk
            return
        async for chunk in self._stream_plain(body):
            yield chunk

    def _handle_plain(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        return self._inference.chat_completion(vllm_body)

    async def _stream_plain(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        vllm_body = _strip_proxy_fields(body)
        async for chunk in passthrough_vllm_stream(self._inference, vllm_body):
            yield chunk

    def _handle_client_functions(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        completion = self._inference.chat_completion(vllm_body)
        return _normalize_tool_calls_completion(completion)

    async def _stream_client_functions(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        vllm_body = _strip_proxy_fields(body)
        async for chunk in passthrough_vllm_stream(self._inference, vllm_body):
            yield chunk

    def _handle_reasoning(self, body: dict[str, Any]) -> dict[str, Any]:
        vllm_body = _strip_proxy_fields(body)
        vllm_body["chat_template_kwargs"] = {"enable_thinking": True}
        completion = self._inference.chat_completion(vllm_body)
        return _passthrough_vllm_reasoning_fields(completion)

    async def _stream_reasoning(self, body: dict[str, Any]) -> AsyncIterator[bytes]:
        vllm_body = _strip_proxy_fields(body)
        vllm_body["chat_template_kwargs"] = {"enable_thinking": True}
        async for chunk in passthrough_vllm_stream(
            self._inference,
            vllm_body,
            map_reasoning=True,
        ):
            yield chunk

    def _handle_system_tool(
        self,
        body: dict[str, Any],
        sys_tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _validate_system_tools(sys_tools)
        tool = sys_tools[0]
        tool_type = str(tool.get("type", ""))
        if tool_type == "web_search":
            return self._handle_web_search(body, tool)
        msg = f"Unsupported system tool: {tool_type}"
        raise ValidationError(msg, code="invalid_request_error")

    async def _stream_system_tool(
        self,
        body: dict[str, Any],
        sys_tools: list[dict[str, Any]],
    ) -> AsyncIterator[bytes]:
        _validate_system_tools(sys_tools)
        tool = sys_tools[0]
        tool_type = str(tool.get("type", ""))
        if tool_type == "web_search":
            async for chunk in self._stream_web_search(body, tool):
                yield chunk
            return
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
        messages = body["messages"]

        orchestrator = self._web_search_orchestrator()
        return orchestrator.run(
            model=body.get("model"),
            messages=messages,
            web_search_tool=tool,
            user_location=user_location,
        )

    async def _stream_web_search(
        self,
        body: dict[str, Any],
        tool: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        user_location = tool.get("user_location")
        if not user_location:
            raise ValidationError(
                "user_location is required for web_search",
                code="missing_required_parameter",
                param="tools[0].user_location",
            )
        messages = body["messages"]

        orchestrator = self._web_search_orchestrator()
        async for chunk in orchestrator.run_stream(
            model=body.get("model"),
            messages=messages,
            web_search_tool=tool,
            user_location=user_location,
        ):
            yield chunk

    def _web_search_orchestrator(self) -> Any:
        mcp_url = self._registry.mcp_url_for("web_search")
        mcp = McpToolClient(mcp_url, timeout_seconds=self._settings.mcp_timeout_seconds)
        return self._registry.create_web_search_orchestrator(
            self._inference,
            mcp,
            default_model=self._settings.default_model,
        )

    @staticmethod
    def _log_dispatch(body: dict[str, Any]) -> None:
        log_route_mode(
            mode=resolve_request_mode(body),
            tool_types=tool_types_from_body(body),
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
