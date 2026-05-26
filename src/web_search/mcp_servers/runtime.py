"""Process-wide MCP runtime (Playwright pool + HTTP clients) for streamable HTTP mode."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import httpx

from web_search.adapters.playwright_pool import PlaywrightBrowserPool
from web_search.adapters.searxng_client import SearxngClient
from web_search.core.settings import LoadedAppConfig, load_app_config
from web_search.mcp_servers.lifespan_state import WebSearchLifespanState


class _SharedRuntimeStore:
    """Mutable holder so HTTP lifespan can set/clear state without ``global``."""

    __slots__ = ("_state",)

    def __init__(self) -> None:
        self._state: WebSearchLifespanState | None = None

    def get(self) -> WebSearchLifespanState:
        if self._state is None:
            msg = "Shared runtime is not initialized (HTTP lifespan not started)"
            raise RuntimeError(msg)
        return self._state

    def set(self, state: WebSearchLifespanState | None) -> None:
        self._state = state


_shared_runtime = _SharedRuntimeStore()


def get_shared_state() -> WebSearchLifespanState:
    return _shared_runtime.get()


def build_runtime_services(loaded: LoadedAppConfig) -> WebSearchLifespanState:
    """Construct shared deps; Playwright pool is **not** started yet."""
    pool = PlaywrightBrowserPool(loaded.limits.playwright)
    client = httpx.AsyncClient(follow_redirects=True)
    searx = SearxngClient(client)
    return WebSearchLifespanState(
        app_config=loaded,
        http_client=client,
        playwright_pool=pool,
        searxng_client=searx,
        limits=loaded.limits,
        fetch_policies=loaded.fetch_policies,
    )


@asynccontextmanager
async def embedded_lifespan(_app: object) -> AsyncIterator[WebSearchLifespanState]:
    """One process-local pool for stdio (single long-lived MCP connection)."""
    loaded = load_app_config()
    state = build_runtime_services(loaded)
    await state.playwright_pool.start()
    try:
        yield state
    finally:
        await state.playwright_pool.stop()
        await state.http_client.aclose()


@asynccontextmanager
async def shared_tool_lifespan(_app: object) -> AsyncIterator[WebSearchLifespanState]:
    """Yield shared state created by ``hold_shared_runtime`` (HTTP / ASGI)."""
    yield get_shared_state()


@asynccontextmanager
async def hold_shared_runtime() -> AsyncIterator[None]:
    """Start pool + clients once for the whole ASGI process lifetime."""
    loaded = load_app_config()
    state = build_runtime_services(loaded)
    await state.playwright_pool.start()
    _shared_runtime.set(state)
    try:
        yield
    finally:
        await state.playwright_pool.stop()
        await state.http_client.aclose()
        _shared_runtime.set(None)
