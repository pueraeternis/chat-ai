"""MCP streamable HTTP client for system tool primitives."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import httpx
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from core.errors import McpToolError
from core.log_events import log_event, log_upstream_error

_MCP_LOGGER = logging.getLogger("chat_proxy.upstream")


def _parse_tool_dict(result: types.CallToolResult) -> dict[str, Any]:
    if result.structuredContent is not None:
        return dict(result.structuredContent)
    chunks: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            chunks.append(block.text)
    raw = "\n".join(chunks).strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class McpToolClient:
    """Call named tools on a single MCP HTTP server."""

    def __init__(self, mcp_url: str, *, timeout_seconds: float = 180.0) -> None:
        self._mcp_url = mcp_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke MCP tool and return structured dict payload."""
        read_td = timedelta(seconds=self._timeout_seconds)
        httpx_timeout = httpx.Timeout(
            connect=15.0,
            read=self._timeout_seconds + 30.0,
            write=120.0,
            pool=30.0,
        )
        started = time.perf_counter()
        try:
            async with (
                httpx.AsyncClient(follow_redirects=True, timeout=httpx_timeout) as http_client,
                streamable_http_client(self._mcp_url, http_client=http_client) as (
                    read_stream,
                    write_stream,
                    _sid,
                ),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=read_td,
                    client_info=types.Implementation(name="chat-proxy", version="0.1.0"),
                ) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=read_td,
                )
        except Exception as exc:
            log_upstream_error(stage="mcp", tool=name, exc=exc)
            raise McpToolError(f"MCP {name!r} failed: {exc}") from exc

        duration_ms = (time.perf_counter() - started) * 1000
        log_event(
            _MCP_LOGGER,
            "mcp_tool_call",
            level=logging.DEBUG,
            tool=name,
            duration_ms=round(duration_ms, 2),
        )

        if result.isError:
            err = McpToolError(f"MCP {name!r} returned isError")
            log_upstream_error(stage="mcp", tool=name, exc=err)
            raise err
        payload = _parse_tool_dict(result)
        if not payload.get("ok", True):
            err = McpToolError(
                f"MCP {name!r} error: {payload.get('code')}: {payload.get('message')}",
            )
            log_upstream_error(stage="mcp", tool=name, exc=err)
            raise err
        return payload

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Blocking wrapper; safe from sync code and from FastAPI async handlers."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.call_tool(name, arguments))
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                lambda: asyncio.run(self.call_tool(name, arguments)),
            ).result()
