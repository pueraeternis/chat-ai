"""Use-case: metasearch via SearXNG and shaped URL hits."""

from __future__ import annotations

from typing import Any

from web_search.adapters.searxng_client import SearxngClient
from web_search.core.errors import SearchError
from web_search.core.limits_config import LimitsConfig
from web_search.core.search_types import SearchUrlHit, SearchUrlsResult

CODE_SEARXNG_INVALID_RESPONSE = "SEARXNG_INVALID_RESPONSE"
CODE_SEARCH_INTERNAL_ERROR = "SEARCH_INTERNAL_ERROR"


async def search_urls(
    *,
    searxng: SearxngClient,
    limits: LimitsConfig,
    query: str,
    language: str,
    max_results: int | None,
    categories: str | None,
    safe_search: int | None,
) -> SearchUrlsResult:
    defaults = limits.search_urls_defaults
    eff_max = max_results if max_results is not None else defaults.max_results
    eff_max = min(max(eff_max, 1), defaults.max_results_cap)
    eff_categories = categories if categories is not None else defaults.categories
    eff_safe = safe_search if safe_search is not None else defaults.safe_search

    try:
        data = await searxng.get_search_json(
            base_url=limits.searxng.base_url,
            timeout_seconds=limits.searxng.request_timeout_seconds,
            q=query,
            language=language,
            categories=eff_categories,
            safesearch=eff_safe,
        )
        hits = _extract_hits(data, limit=eff_max)
        return SearchUrlsResult(ok=True, query=query, results=hits)
    except SearchError as exc:
        return SearchUrlsResult(
            ok=False,
            code=exc.code,
            message=exc.message,
            query=query,
            results=[],
        )
    except Exception as exc:  # pragma: no cover - defensive
        return SearchUrlsResult(
            ok=False,
            code=CODE_SEARCH_INTERNAL_ERROR,
            message=str(exc),
            query=query,
            results=[],
        )


def _extract_hits(data: dict[str, Any], *, limit: int) -> list[SearchUrlHit]:
    raw = data.get("results")
    if raw is None:
        raise SearchError("SearXNG JSON missing 'results' field", CODE_SEARXNG_INVALID_RESPONSE)
    if not isinstance(raw, list):
        raise SearchError("SearXNG 'results' must be a list", CODE_SEARXNG_INVALID_RESPONSE)

    out: list[SearchUrlHit] = []
    for row in raw:
        if len(out) >= limit:
            break
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        title = row.get("title")
        content = row.get("content")
        engine = row.get("engine")
        out.append(
            SearchUrlHit(
                url=url.strip(),
                title=title if isinstance(title, str) else None,
                content=content if isinstance(content, str) else None,
                engine=engine if isinstance(engine, str) else None,
            ),
        )
    return out
