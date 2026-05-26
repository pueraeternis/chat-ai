"""Map public system tool types to MCP servers and orchestrators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from operations.web_search_pipeline import WebSearchOrchestrator

if TYPE_CHECKING:
    from adapters.mcp_tool_client import McpToolClient
    from core.ports import InferencePort


SYSTEM_TOOL_TYPES = frozenset({"web_search"})


@dataclass(frozen=True)
class SystemToolBinding:
    tool_type: str
    mcp_url: str


class SystemToolRegistry:
    """Resolve system tool type to MCP base URL."""

    def __init__(self, bindings: dict[str, SystemToolBinding]) -> None:
        self._bindings = bindings

    def mcp_url_for(self, tool_type: str) -> str:
        binding = self._bindings.get(tool_type)
        if binding is None:
            msg = f"Unknown system tool type: {tool_type}"
            raise KeyError(msg)
        return binding.mcp_url

    def create_web_search_orchestrator(
        self,
        inference: InferencePort,
        mcp_client: McpToolClient,
        *,
        default_model: str,
    ) -> WebSearchOrchestrator:
        return WebSearchOrchestrator(
            inference=inference,
            mcp=mcp_client,
            default_model=default_model,
        )
