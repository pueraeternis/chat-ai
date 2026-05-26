"""Lightweight tests for ``PlaywrightBrowserPool`` without launching Chromium."""

from __future__ import annotations

import pytest

from web_search.adapters.playwright_pool import CODE_FETCH_PLAYWRIGHT_START, PlaywrightBrowserPool
from web_search.core.errors import FetchError
from web_search.core.limits_config import PlaywrightLimits


def _limits(**kwargs: object) -> PlaywrightLimits:
    base = {
        "navigation_timeout_ms": 30_000,
        "max_redirects": 10,
        "max_concurrent_contexts": 1,
        "context_queue_wait_timeout_seconds": 0.1,
    }
    base.update(kwargs)
    return PlaywrightLimits.model_validate(base)


@pytest.mark.asyncio
async def test_acquire_page_before_start_raises() -> None:
    pool = PlaywrightBrowserPool(_limits())
    with pytest.raises(FetchError) as exc:
        async with pool.acquire_page():
            pass  # pragma: no cover
    assert exc.value.code == CODE_FETCH_PLAYWRIGHT_START
    assert "not started" in exc.value.message.lower()
