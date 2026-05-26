"""MCP tool mapping: ``search_urls`` -> ``operations.search_urls``."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from web_search.core.search_types import SearchUrlsResult
from web_search.mcp_servers.lifespan_state import WebSearchLifespanState
from web_search.operations import search_urls as search_urls_op


def register_search_urls_tool(mcp: FastMCP[WebSearchLifespanState]) -> None:
    description = (
        "Run a metasearch query against SearXNG and return result URLs (and optional snippets). "
        "Arguments ``query`` and ``language`` are required; ``language`` must be a SearXNG locale "
        "code (e.g. en-US, ru-RU). Optional fields fall back to server defaults from config."
    )

    async def search_urls(
        query: Annotated[
            str,
            Field(min_length=1, max_length=4096, description="Search query text."),
        ],
        language: Annotated[
            str,
            Field(
                min_length=2,
                max_length=32,
                description="SearXNG language/locale code (e.g. en-US, ru-RU).",
            ),
        ],
        ctx: Context,
        max_results: Annotated[
            int | None,
            Field(
                default=None,
                ge=1,
                le=200,
                description="Max URLs to return (capped by server config).",
            ),
        ] = None,
        categories: Annotated[
            str | None,
            Field(
                default=None,
                max_length=256,
                description="SearXNG categories string (e.g. general).",
            ),
        ] = None,
        safe_search: Annotated[
            int | None,
            Field(default=None, ge=0, le=2, description="SearXNG safesearch level 0-2."),
        ] = None,
    ) -> SearchUrlsResult:
        state: WebSearchLifespanState = ctx.request_context.lifespan_context
        return await search_urls_op.search_urls(
            searxng=state.searxng_client,
            limits=state.limits,
            query=query,
            language=language,
            max_results=max_results,
            categories=categories,
            safe_search=safe_search,
        )

    mcp.add_tool(
        search_urls,
        name="search_urls",
        description=description,
        structured_output=True,
    )
