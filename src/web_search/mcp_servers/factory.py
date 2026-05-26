"""Build configured ``FastMCP`` server instances."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from web_search.mcp_servers.lifespan_state import WebSearchLifespanState
from web_search.mcp_servers.runtime import embedded_lifespan, shared_tool_lifespan
from web_search.mcp_servers.tools_fetch_pages import register_fetch_page_tools
from web_search.mcp_servers.tools_search_urls import register_search_urls_tool


def create_web_search_mcp(*, http_mode: bool = False) -> FastMCP[WebSearchLifespanState]:
    """
    Create FastMCP server for stdio or HTTP mode.

    ``http_mode=True`` uses shared process state (started by the ASGI outer lifespan);
    ``http_mode=False`` (stdio) starts Playwright inside the MCP connection lifespan.
    """
    lifespan = shared_tool_lifespan if http_mode else embedded_lifespan
    mcp: FastMCP[WebSearchLifespanState] = FastMCP[WebSearchLifespanState](
        "web-search-mcp",
        instructions="Web search (search_urls via SearXNG) and page fetch (fetch_page_html, fetch_page_markdown via Playwright).",
        lifespan=lifespan,
    )
    register_search_urls_tool(mcp)
    register_fetch_page_tools(mcp)
    return mcp
