"""HTTP client for SearXNG ``/search`` JSON API."""

from __future__ import annotations

from typing import Any

import httpx

from web_search.core.errors import SearchError

CODE_SEARXNG_TIMEOUT = "SEARXNG_TIMEOUT"
CODE_SEARXNG_UNAVAILABLE = "SEARXNG_UNAVAILABLE"
CODE_SEARXNG_FORBIDDEN = "SEARXNG_FORBIDDEN"
CODE_SEARXNG_CLIENT_ERROR = "SEARXNG_CLIENT_ERROR"
CODE_SEARXNG_SERVER_ERROR = "SEARXNG_SERVER_ERROR"
CODE_SEARXNG_INVALID_RESPONSE = "SEARXNG_INVALID_RESPONSE"


class SearxngClient:
    """Thin async GET wrapper; maps transport failures to ``SearchError``."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_search_json(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        q: str,
        language: str,
        categories: str,
        safesearch: int,
    ) -> dict[str, Any]:
        root = base_url.rstrip("/")
        url = f"{root}/search"
        params = {
            "q": q,
            "format": "json",
            "language": language,
            "categories": categories,
            "safesearch": str(safesearch),
        }
        try:
            response = await self._http.get(url, params=params, timeout=timeout_seconds)
        except httpx.TimeoutException as exc:
            raise SearchError("SearXNG request timed out", CODE_SEARXNG_TIMEOUT) from exc
        except httpx.RequestError as exc:
            raise SearchError("SearXNG instance is unreachable", CODE_SEARXNG_UNAVAILABLE) from exc

        if response.status_code == 403:
            raise SearchError(
                "SearXNG refused JSON output (check search.formats includes json in settings.yml)",
                CODE_SEARXNG_FORBIDDEN,
            )
        if 400 <= response.status_code < 500:
            raise SearchError(
                f"SearXNG client error: HTTP {response.status_code}",
                CODE_SEARXNG_CLIENT_ERROR,
            )
        if response.status_code >= 500:
            raise SearchError(
                f"SearXNG server error: HTTP {response.status_code}",
                CODE_SEARXNG_SERVER_ERROR,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SearchError(
                "SearXNG response is not valid JSON",
                CODE_SEARXNG_INVALID_RESPONSE,
            ) from exc

        if not isinstance(data, dict):
            raise SearchError("SearXNG JSON root must be an object", CODE_SEARXNG_INVALID_RESPONSE)
        return data
