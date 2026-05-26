"""Shared Playwright browser pool (bounded contexts + page checkout)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from web_search.core.errors import FetchError
from web_search.core.limits_config import PlaywrightLimits

CODE_FETCH_CONTEXT_QUEUE_TIMEOUT = "FETCH_CONTEXT_QUEUE_TIMEOUT"
CODE_FETCH_PLAYWRIGHT_START = "FETCH_PLAYWRIGHT_START"


class PlaywrightBrowserPool:
    """Pre-created Chromium contexts with a bounded queue for concurrent fetches."""

    def __init__(self, limits: PlaywrightLimits) -> None:
        self._limits = limits
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._contexts: asyncio.Queue[BrowserContext] | None = None

    async def start(self) -> None:
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment specific
            raise FetchError(
                f"Playwright failed to start: {exc}",
                CODE_FETCH_PLAYWRIGHT_START,
            ) from exc

        self._playwright = playwright
        self._browser = browser
        n = self._limits.max_concurrent_contexts
        self._contexts = asyncio.Queue(maxsize=n)
        for _ in range(n):
            ctx = await browser.new_context()
            await self._contexts.put(ctx)

    async def stop(self) -> None:
        # Closing the browser tears down all contexts (including any still queued).
        self._contexts = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    @asynccontextmanager
    async def acquire_page(self) -> AsyncIterator[Page]:
        if self._contexts is None or self._browser is None:
            raise FetchError("Playwright pool is not started", CODE_FETCH_PLAYWRIGHT_START)

        try:
            ctx = await asyncio.wait_for(
                self._contexts.get(),
                timeout=self._limits.context_queue_wait_timeout_seconds,
            )
        except TimeoutError as exc:
            raise FetchError(
                "Timed out waiting for a free browser context",
                CODE_FETCH_CONTEXT_QUEUE_TIMEOUT,
            ) from exc

        page = await ctx.new_page()
        try:
            yield page
        finally:
            await page.close()
            if self._contexts is not None:
                await self._contexts.put(ctx)
