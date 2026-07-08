"""Tests for fetch operations with mocked Playwright pool."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from web_search.core.errors import UrlFetchPolicyError
from web_search.core.fetch_policies_config import load_fetch_policies_config
from web_search.core.fetch_url_validation import CODE_PRIVATE_NETWORK_FORBIDDEN
from web_search.core.limits_config import LimitsConfig
from web_search.operations.fetch_page_html import (
    fetch_page_html,
    install_fetch_url_policy_route,
    load_html_document,
)
from web_search.operations.fetch_page_markdown import fetch_page_markdown

RouteHandler = Callable[[Any, Any], Awaitable[None]]


def _limits() -> LimitsConfig:
    path = Path(__file__).resolve().parents[3] / "config" / "web_search" / "default.yaml"
    return LimitsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _policies() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "web_search" / "fetch_policies.yaml"


def _policies_config():
    return load_fetch_policies_config(_policies())


def _mock_page(*, final_url: str, content_type: str = "text/html; charset=utf-8", html: str = ""):
    page = MagicMock()
    response = MagicMock()
    response.headers = {"content-type": content_type}
    page.goto = AsyncMock(return_value=response)
    page.url = final_url
    page.route = AsyncMock()
    page.content = AsyncMock(return_value=html)
    return page


@pytest.mark.asyncio
async def test_fetch_page_html_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield _mock_page(
            final_url="https://example.com/final",
            html="<html><body>ok</body></html>",
        )

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
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
        yield _mock_page(
            final_url="https://example.com/doc.pdf",
            content_type="application/pdf",
        )

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/doc.pdf",
    )
    assert out.ok is False
    assert out.code == "UNSUPPORTED_CONTENT_TYPE"
    assert out.content_type == "application/pdf"


@pytest.mark.asyncio
async def test_fetch_page_html_rejects_private_final_url(monkeypatch: pytest.MonkeyPatch) -> None:
    validate = AsyncMock(
        side_effect=[
            None,
            UrlFetchPolicyError("loopback", CODE_PRIVATE_NETWORK_FORBIDDEN),
        ]
    )
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        validate,
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield _mock_page(final_url="http://127.0.0.1/secret")

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/redirect",
    )
    assert out.ok is False
    assert out.code == CODE_PRIVATE_NETWORK_FORBIDDEN
    assert out.final_url == "http://127.0.0.1/secret"


@pytest.mark.asyncio
async def test_fetch_page_html_allows_public_redirect_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        validate,
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield _mock_page(
            final_url="https://cdn.example.com/final",
            html="<html><body>redirected</body></html>",
        )

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_html(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/start",
    )
    assert out.ok is True
    assert out.final_url == "https://cdn.example.com/final"
    assert validate.await_count == 2


@pytest.mark.asyncio
async def test_install_fetch_url_policy_route_aborts_unsafe_subresource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate = AsyncMock(
        side_effect=UrlFetchPolicyError("private", CODE_PRIVATE_NETWORK_FORBIDDEN),
    )
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        validate,
    )

    page = MagicMock()
    handler: RouteHandler | None = None

    async def capture_route(_pattern: Any, callback: RouteHandler) -> None:
        nonlocal handler
        handler = callback

    page.route = capture_route

    await install_fetch_url_policy_route(page, _policies_config())
    assert handler is not None

    route = MagicMock()
    route.abort = AsyncMock()
    route.continue_ = AsyncMock()
    request = MagicMock()
    request.url = "http://127.0.0.1/asset.js"

    await handler(route, request)
    route.abort.assert_awaited_once()
    route.continue_.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_fetch_url_policy_route_continues_public_subresource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    page = MagicMock()
    handler: RouteHandler | None = None

    async def capture_route(_pattern: Any, callback: RouteHandler) -> None:
        nonlocal handler
        handler = callback

    page.route = capture_route

    await install_fetch_url_policy_route(page, _policies_config())
    assert handler is not None

    route = MagicMock()
    route.abort = AsyncMock()
    route.continue_ = AsyncMock()
    request = MagicMock()
    request.url = "https://cdn.example.com/app.js"

    await handler(route, request)
    route.continue_.assert_awaited_once()
    route.abort.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_html_document_installs_route_before_goto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )
    page = _mock_page(
        final_url="https://example.com/",
        html="<html><body>ok</body></html>",
    )
    call_order: list[str] = []

    async def route_side_effect(*_args, **_kwargs):
        call_order.append("route")

    page.route = AsyncMock(side_effect=route_side_effect)

    async def goto_side_effect(*_args, **_kwargs):
        call_order.append("goto")
        response = MagicMock()
        response.headers = {"content-type": "text/html"}
        return response

    page.goto = AsyncMock(side_effect=goto_side_effect)

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield page

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await load_html_document(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/",
    )
    assert out.ok is True
    assert call_order == ["route", "goto"]


@pytest.mark.asyncio
async def test_fetch_page_markdown_runs_trafilatura(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_markdown.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield _mock_page(
            final_url="https://example.com/",
            content_type="text/html",
            html="<html><body><p>Hello world</p></body></html>",
        )

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_markdown(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/",
    )
    assert out.ok is True
    assert out.markdown
    assert "Hello" in out.markdown


@pytest.mark.asyncio
async def test_fetch_page_markdown_propagates_private_final_url_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "web_search.operations.fetch_page_markdown.validate_fetch_url_before_fetch_async",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "web_search.operations.fetch_page_html.validate_fetch_url_before_fetch_async",
        AsyncMock(
            side_effect=UrlFetchPolicyError("loopback", CODE_PRIVATE_NETWORK_FORBIDDEN),
        ),
    )

    @asynccontextmanager
    async def acquire_page() -> AsyncIterator[MagicMock]:
        yield _mock_page(final_url="http://127.0.0.1/secret")

    pool = MagicMock()
    pool.acquire_page = acquire_page

    out = await fetch_page_markdown(
        pool=pool,
        limits=_limits(),
        policies=_policies_config(),
        url="https://example.com/redirect",
    )
    assert out.ok is False
    assert out.code == CODE_PRIVATE_NETWORK_FORBIDDEN
