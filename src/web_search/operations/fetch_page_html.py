"""Use-case: load a public page via Playwright and return rendered HTML."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from web_search.adapters.playwright_pool import PlaywrightBrowserPool
from web_search.core.document_content_type import main_document_is_html
from web_search.core.errors import FetchError, UrlFetchPolicyError
from web_search.core.fetch_policies_config import FetchPoliciesConfig
from web_search.core.fetch_types import FetchPageHtmlResult
from web_search.core.fetch_url_validation import validate_fetch_url_before_fetch_async
from web_search.core.limits_config import LimitsConfig
from web_search.core.utf8_byte_budget import truncate_utf8_to_byte_budget

CODE_FETCH_NAVIGATION_TIMEOUT = "FETCH_NAVIGATION_TIMEOUT"
CODE_UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
CODE_FETCH_PLAYWRIGHT_ERROR = "FETCH_PLAYWRIGHT_ERROR"
CODE_FETCH_INTERNAL_ERROR = "FETCH_INTERNAL_ERROR"

_FETCH_POLICY_LOGGER = logging.getLogger(__name__)


async def install_fetch_url_policy_route(page: Page, policies: FetchPoliciesConfig) -> None:
    """Abort Playwright subresource requests that violate fetch URL policy."""

    async def _handle_route(route, request) -> None:
        try:
            await validate_fetch_url_before_fetch_async(request.url, policies)
        except UrlFetchPolicyError as exc:
            hostname = urlsplit(request.url).hostname or "<unknown>"
            _FETCH_POLICY_LOGGER.debug(
                "Aborting blocked fetch request host=%s code=%s",
                hostname,
                exc.code,
            )
            await route.abort()
            return
        await route.continue_()

    await page.route("**/*", _handle_route)


async def fetch_page_html(
    *,
    pool: PlaywrightBrowserPool,
    limits: LimitsConfig,
    policies: FetchPoliciesConfig,
    url: str,
) -> FetchPageHtmlResult:
    try:
        await validate_fetch_url_before_fetch_async(url, policies)
    except UrlFetchPolicyError as exc:
        return FetchPageHtmlResult(
            ok=False,
            code=exc.code,
            message=exc.message,
            url=url,
        )
    except Exception as exc:  # pragma: no cover
        return FetchPageHtmlResult(
            ok=False,
            code=CODE_FETCH_INTERNAL_ERROR,
            message=str(exc),
            url=url,
        )

    try:
        return await load_html_document(pool=pool, limits=limits, policies=policies, url=url)
    except FetchError as exc:
        return FetchPageHtmlResult(
            ok=False,
            code=exc.code,
            message=exc.message,
            url=url,
        )
    except Exception as exc:  # pragma: no cover
        return FetchPageHtmlResult(
            ok=False,
            code=CODE_FETCH_INTERNAL_ERROR,
            message=str(exc),
            url=url,
        )


async def load_html_document(
    *,
    pool: PlaywrightBrowserPool,
    limits: LimitsConfig,
    policies: FetchPoliciesConfig,
    url: str,
) -> FetchPageHtmlResult:
    """Shared HTML load for ``fetch_page_html`` and ``fetch_page_markdown``."""
    timeout_ms = limits.playwright.navigation_timeout_ms
    async with pool.acquire_page() as page:
        await install_fetch_url_policy_route(page, policies)
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise FetchError("Navigation timed out", CODE_FETCH_NAVIGATION_TIMEOUT) from exc
        except Exception as exc:  # pragma: no cover - browser specific
            raise FetchError(f"Navigation failed: {exc}", CODE_FETCH_PLAYWRIGHT_ERROR) from exc

        final_url = page.url
        try:
            await validate_fetch_url_before_fetch_async(final_url, policies)
        except UrlFetchPolicyError as exc:
            return FetchPageHtmlResult(
                ok=False,
                code=exc.code,
                message=exc.message,
                url=url,
                final_url=final_url,
            )

        content_type = response.headers.get("content-type") if response is not None else None
        if not main_document_is_html(content_type):
            return FetchPageHtmlResult(
                ok=False,
                code=CODE_UNSUPPORTED_CONTENT_TYPE,
                message=f"Document is not HTML (content-type={content_type!r})",
                url=url,
                final_url=final_url,
                content_type=content_type,
            )

        try:
            html = await page.content()
        except Exception as exc:  # pragma: no cover
            raise FetchError(
                f"Failed to read page HTML: {exc}",
                CODE_FETCH_PLAYWRIGHT_ERROR,
            ) from exc

    original_bytes = len(html.encode("utf-8"))
    max_bytes = limits.fetch.max_html_bytes
    html_out, truncated, _ = truncate_utf8_to_byte_budget(html, max_bytes)
    returned_bytes = len(html_out.encode("utf-8"))

    return FetchPageHtmlResult(
        ok=True,
        url=url,
        final_url=final_url,
        content_type=content_type,
        html=html_out,
        truncated=truncated,
        html_byte_length_original=original_bytes,
        html_byte_length_returned=returned_bytes,
    )
