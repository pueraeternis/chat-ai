"""ASGI entry: MCP streamable HTTP + ``GET /health``."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from functools import cache
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse

from core.settings import DEFAULT_BIND_HOST
from web_search.mcp_servers.factory import create_web_search_mcp
from web_search.mcp_servers.lifespan_state import WebSearchLifespanState
from web_search.mcp_servers.runtime import hold_shared_runtime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from mcp.server.fastmcp import FastMCP
    from starlette.requests import Request

def build_http_app() -> Starlette:
    """Starlette app with MCP on ``/mcp`` (default) and ``GET /health``."""
    mcp: FastMCP[WebSearchLifespanState] = create_web_search_mcp(http_mode=True)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "web-search-mcp"})

    inner = mcp.streamable_http_app()

    @asynccontextmanager
    async def merged_lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with hold_shared_runtime(), mcp.session_manager.run():
            yield

    return Starlette(
        routes=list(inner.router.routes),
        lifespan=merged_lifespan,
        middleware=list(inner.user_middleware),
        debug=inner.debug,
    )


@cache
def get_http_app() -> Starlette:
    return build_http_app()


def __getattr__(name: str) -> Starlette:
    """Lazy ``app`` for ``uvicorn mcp_servers.http_asgi:app`` without building at import time."""
    if name == "app":
        return get_http_app()
    raise AttributeError(name)


def main() -> None:
    """Run with ``uv run web-search-mcp-http`` or ``python -m mcp_servers.http_asgi``."""
    # Override bind with WEB_SEARCH_HOST (e.g. 127.0.0.1 for local dev).
    host = os.environ.get("WEB_SEARCH_HOST", DEFAULT_BIND_HOST)
    port = int(os.environ.get("WEB_SEARCH_PORT", "3333"))
    uvicorn.run(get_http_app(), host=host, port=port, factory=False)


if __name__ == "__main__":
    main()
