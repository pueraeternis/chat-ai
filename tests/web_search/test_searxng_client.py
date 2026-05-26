"""Unit tests for ``SearxngClient`` (httpx mocks + JSON fixture)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from web_search.adapters.searxng_client import (
    CODE_SEARXNG_CLIENT_ERROR,
    CODE_SEARXNG_FORBIDDEN,
    CODE_SEARXNG_INVALID_RESPONSE,
    CODE_SEARXNG_SERVER_ERROR,
    CODE_SEARXNG_TIMEOUT,
    CODE_SEARXNG_UNAVAILABLE,
    SearxngClient,
)
from web_search.core.errors import SearchError

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "searxng_search_min.json"


@pytest.mark.asyncio
async def test_get_search_json_loads_fixture_payload() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert str(request.url).startswith("http://searx.test/search")
        assert request.url.params["q"] == "hello"
        assert request.url.params["format"] == "json"
        assert request.url.params["language"] == "en-US"
        assert request.url.params["categories"] == "general"
        assert request.url.params["safesearch"] == "0"
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        out = await client.get_search_json(
            base_url="http://searx.test/",
            timeout_seconds=5.0,
            q="hello",
            language="en-US",
            categories="general",
            safesearch=0,
        )
    assert out["query"] == "example query"
    assert len(out["results"]) == 2
    assert out["results"][0]["url"] == "https://example.org/page"


@pytest.mark.asyncio
async def test_get_search_json_strips_trailing_slash_on_base_url() -> None:
    called: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        called["host"] = str(request.url).split("/search")[0]
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        await client.get_search_json(
            base_url="https://sx.example///",
            timeout_seconds=1.0,
            q="x",
            language="ru-RU",
            categories="images",
            safesearch=2,
        )
    assert called["host"] == "https://sx.example"


@pytest.mark.asyncio
async def test_timeout_maps_to_search_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("deadline", request=None)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        with pytest.raises(SearchError) as exc:
            await client.get_search_json(
                base_url="http://x",
                timeout_seconds=0.01,
                q="q",
                language="en-US",
                categories="general",
                safesearch=0,
            )
    assert exc.value.code == CODE_SEARXNG_TIMEOUT


@pytest.mark.asyncio
async def test_request_error_maps_to_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=None)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        with pytest.raises(SearchError) as exc:
            await client.get_search_json(
                base_url="http://x",
                timeout_seconds=1.0,
                q="q",
                language="en-US",
                categories="general",
                safesearch=0,
            )
    assert exc.value.code == CODE_SEARXNG_UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (403, CODE_SEARXNG_FORBIDDEN),
        (404, CODE_SEARXNG_CLIENT_ERROR),
        (418, CODE_SEARXNG_CLIENT_ERROR),
        (500, CODE_SEARXNG_SERVER_ERROR),
        (503, CODE_SEARXNG_SERVER_ERROR),
    ],
)
async def test_http_status_maps_to_search_error(status: int, code: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="err")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        with pytest.raises(SearchError) as exc:
            await client.get_search_json(
                base_url="http://x",
                timeout_seconds=1.0,
                q="q",
                language="en-US",
                categories="general",
                safesearch=0,
            )
    assert exc.value.code == code


@pytest.mark.asyncio
async def test_invalid_json_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json {[")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        with pytest.raises(SearchError) as exc:
            await client.get_search_json(
                base_url="http://x",
                timeout_seconds=1.0,
                q="q",
                language="en-US",
                categories="general",
                safesearch=0,
            )
    assert exc.value.code == CODE_SEARXNG_INVALID_RESPONSE


@pytest.mark.asyncio
async def test_json_array_root_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SearxngClient(http)
        with pytest.raises(SearchError) as exc:
            await client.get_search_json(
                base_url="http://x",
                timeout_seconds=1.0,
                q="q",
                language="en-US",
                categories="general",
                safesearch=0,
            )
    assert exc.value.code == CODE_SEARXNG_INVALID_RESPONSE
