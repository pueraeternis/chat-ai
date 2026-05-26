"""Tests for ``operations.search_urls`` (mocked SearXNG HTTP)."""

from pathlib import Path

import httpx
import pytest
import yaml

from web_search.adapters.searxng_client import SearxngClient
from web_search.core.limits_config import LimitsConfig
from web_search.operations.search_urls import search_urls


def _minimal_limits(base_url: str = "http://searx.test") -> LimitsConfig:
    path = Path(__file__).resolve().parents[3] / "config" / "web_search" / "default.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["searxng"]["base_url"] = base_url
    return LimitsConfig.model_validate(data)


@pytest.mark.asyncio
async def test_search_urls_maps_and_truncates_results() -> None:
    payload = {
        "results": [
            {"url": "https://a.example", "title": "A", "content": "snippet", "engine": "dummy"},
            {"url": "https://b.example", "title": "B"},
            {"url": "https://c.example", "title": "C"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "hello"
        assert request.url.params["format"] == "json"
        assert request.url.params["language"] == "en-US"
        assert request.url.params["categories"] == "general"
        assert request.url.params["safesearch"] == "1"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await search_urls(
            searxng=SearxngClient(client),
            limits=_minimal_limits(),
            query="hello",
            language="en-US",
            max_results=2,
            categories=None,
            safe_search=1,
        )
    assert out.ok is True
    assert len(out.results) == 2
    assert out.results[0].url == "https://a.example"
    assert out.results[0].engine == "dummy"


@pytest.mark.asyncio
async def test_search_urls_returns_error_dto_on_searxng_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await search_urls(
            searxng=SearxngClient(client),
            limits=_minimal_limits(),
            query="x",
            language="ru-RU",
            max_results=None,
            categories=None,
            safe_search=None,
        )
    assert out.ok is False
    assert out.code == "SEARXNG_FORBIDDEN"
    assert out.query == "x"
    assert out.results == []
