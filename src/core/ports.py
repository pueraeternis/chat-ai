"""Ports (interfaces) for infrastructure adapters."""

from __future__ import annotations

from typing import Any, Protocol


class InferencePort(Protocol):
    """OpenAI-compatible chat completions against vLLM."""

    def list_models(self) -> dict[str, Any]:
        """GET /v1/models response body."""
        ...

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/chat/completions response body."""
        ...
