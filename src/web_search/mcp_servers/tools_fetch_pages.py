"""MCP tools: ``fetch_page_html`` and ``fetch_page_markdown``."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from web_search.core.fetch_types import FetchPageHtmlResult, FetchPageMarkdownResult
from web_search.mcp_servers.lifespan_state import WebSearchLifespanState
from web_search.operations import fetch_page_html as fetch_page_html_op
from web_search.operations import fetch_page_markdown as fetch_page_markdown_op


def register_fetch_page_tools(mcp: FastMCP[WebSearchLifespanState]) -> None:
    html_desc = (
        "Load a public web page with headless Chromium and return the rendered HTML as a UTF-8 string. "
        "URL must pass server fetch policies (internet-only, DNS/IP checks). "
        "Non-HTML documents return UNSUPPORTED_CONTENT_TYPE."
    )

    async def fetch_page_html(
        url: Annotated[
            str,
            Field(min_length=4, max_length=8192, description="http(s) URL to fetch."),
        ],
        ctx: Context,
    ) -> FetchPageHtmlResult:
        state = ctx.request_context.lifespan_context
        return await fetch_page_html_op.fetch_page_html(
            pool=state.playwright_pool,
            limits=state.limits,
            policies=state.fetch_policies,
            url=url,
        )

    md_desc = (
        "Load a public web page with headless Chromium, then extract main text as Markdown via trafilatura. "
        "Same URL policies and size limits as fetch_page_html for the HTML stage."
    )

    async def fetch_page_markdown(
        url: Annotated[
            str,
            Field(min_length=4, max_length=8192, description="http(s) URL to fetch."),
        ],
        ctx: Context,
    ) -> FetchPageMarkdownResult:
        state = ctx.request_context.lifespan_context
        return await fetch_page_markdown_op.fetch_page_markdown(
            pool=state.playwright_pool,
            limits=state.limits,
            policies=state.fetch_policies,
            url=url,
        )

    mcp.add_tool(
        fetch_page_html,
        name="fetch_page_html",
        description=html_desc,
        structured_output=True,
    )
    mcp.add_tool(
        fetch_page_markdown,
        name="fetch_page_markdown",
        description=md_desc,
        structured_output=True,
    )
