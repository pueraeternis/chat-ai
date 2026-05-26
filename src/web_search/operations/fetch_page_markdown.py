"""Use-case: load a page and extract main text as Markdown (trafilatura)."""

from __future__ import annotations

import trafilatura

from web_search.adapters.playwright_pool import PlaywrightBrowserPool
from web_search.core.errors import UrlFetchPolicyError
from web_search.core.fetch_policies_config import FetchPoliciesConfig
from web_search.core.fetch_types import FetchPageMarkdownResult
from web_search.core.fetch_url_validation import validate_fetch_url_before_fetch_async
from web_search.core.limits_config import LimitsConfig
from web_search.operations.fetch_page_html import (
    CODE_FETCH_INTERNAL_ERROR,
    CODE_FETCH_PLAYWRIGHT_ERROR,
    load_html_document,
)


async def fetch_page_markdown(
    *,
    pool: PlaywrightBrowserPool,
    limits: LimitsConfig,
    policies: FetchPoliciesConfig,
    url: str,
) -> FetchPageMarkdownResult:
    try:
        await validate_fetch_url_before_fetch_async(url, policies)
    except UrlFetchPolicyError as exc:
        return FetchPageMarkdownResult(
            ok=False,
            code=exc.code,
            message=exc.message,
            url=url,
        )
    except Exception as exc:  # pragma: no cover
        return FetchPageMarkdownResult(
            ok=False,
            code=CODE_FETCH_INTERNAL_ERROR,
            message=str(exc),
            url=url,
        )

    try:
        html_payload = await load_html_document(pool=pool, limits=limits, url=url)
    except Exception as exc:  # pragma: no cover
        return FetchPageMarkdownResult(
            ok=False,
            code=CODE_FETCH_INTERNAL_ERROR,
            message=str(exc),
            url=url,
        )

    if not html_payload.ok or html_payload.html is None:
        return FetchPageMarkdownResult(
            ok=False,
            code=html_payload.code or CODE_FETCH_PLAYWRIGHT_ERROR,
            message=html_payload.message or "Failed to load HTML for markdown extraction",
            url=url,
            final_url=html_payload.final_url,
            content_type=html_payload.content_type,
        )

    base_url = html_payload.final_url or url
    try:
        md = trafilatura.extract(
            html_payload.html,
            url=base_url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
        )
    except Exception as exc:
        return FetchPageMarkdownResult(
            ok=False,
            code="MARKDOWN_EXTRACT_ERROR",
            message=str(exc),
            url=url,
            final_url=html_payload.final_url,
            content_type=html_payload.content_type,
        )
    text = (md or "").strip()
    original_chars = len(text)
    cap = limits.fetch.markdown_max_chars
    truncated = False
    if original_chars > cap:
        text = text[:cap]
        truncated = True
    return FetchPageMarkdownResult(
        ok=True,
        url=url,
        final_url=html_payload.final_url,
        content_type=html_payload.content_type,
        markdown=text,
        markdown_truncated=truncated,
        markdown_char_length_original=original_chars,
        markdown_char_length_returned=len(text),
    )
