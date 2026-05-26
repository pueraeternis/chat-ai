"""Application error hierarchy for chat-proxy."""

from __future__ import annotations


class AppError(Exception):
    """Base for domain and application errors."""

    def __init__(self, message: str, *, code: str = "internal_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ValidationError(AppError):
    """Request validation failed."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_request_error",
        param: str | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.param = param


class InferenceError(AppError):
    """vLLM or upstream inference failure."""

    def __init__(self, message: str, *, code: str = "inference_error") -> None:
        super().__init__(message, code=code)


class McpToolError(AppError):
    """MCP tool call failed."""

    def __init__(self, message: str, *, code: str = "mcp_tool_error") -> None:
        super().__init__(message, code=code)
