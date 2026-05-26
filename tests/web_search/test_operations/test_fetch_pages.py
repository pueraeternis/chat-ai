"""Tests for fetch operations with mocked Playwright pool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from web_search.core.fetch_policies_config import load_fetch_policies_config
from web_search.core.limits_config import LimitsConfig
from web_search.operations.fetch_page_html import fetch_page_html
from web_search.operations.fetch_page_markdown import fetch_page_markdown


def _limits() -> LimitsConfig:
    path = Path(__file__).resolve().parents[3] / "config" / "web_search" / "default.yaml"
    return LimitsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _policies() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "web_search" / "fetch_policies.yaml"


@pytest.mark.asyncio
async def test_fetch_page_html_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        page = MagicMock()
        response = MagicMock()
        response.headers = {"content-type": "text/html; charset=utf-8"}
        page.goto = AsyncMock(return_value=response)
        page.url = "https://example.com/final"
        page.content = AsyncMock(return_value="<html><body>ok</body></html>")
        yield page

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=load_fetch_policies_config(_policies()),
        url="https://example.com/",
    )
    assert out.ok is True
    assert out.html == "<html><body>ok</body></html>"
    assert out.final_url == "https://example.com/final"
    assert out.truncated is False


@pytest.mark.asyncio
async def test_fetch_page_html_unsupported_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        page = MagicMock()
        response = MagicMock()
        response.headers = {"content-type": "application/pdf"}
        page.goto = AsyncMock(return_value=response)
        page.url = "https://example.com/doc.pdf"
        yield page

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=load_fetch_policies_config(_policies()),
        url="https://example.com/doc.pdf",
    )
    assert out.ok is False
    assert out.code == "UNSUPPORTED_CONTENT_TYPE"
    assert out.content_type == "application/pdf"


@pytest.mark.asyncio
async def test_fetch_page_markdown_runs_trafilatura(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_markdown.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        page = MagicMock()
        response = MagicMock()
        response.headers = {"content-type": "text/html"}
        page.goto = AsyncMock(return_value=response)
        page.url = "https://example.com/"
        page.content = AsyncMock(return_value="<html><body><p>Hello world</p></body></html>")
        yield page

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_markdown(
        pool=pool,
        limits=_limits(),
        policies=load_fetch_policies_config(_policies()),
        url="https://example.com/",
    )
    assert out.ok is True
    assert out.markdown
    assert "Hello" in out.markdown
