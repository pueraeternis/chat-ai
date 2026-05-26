"""Web search orchestration (steps 0-5) via MCP + vLLM."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from adapters.mcp_tool_client import McpToolClient
from core.ports import InferencePort
from core.web_search_logging import (
    log_fetch_results,
    log_router_result,
    log_search_hits,
    log_search_no_hits,
    log_url_filter_result,
    log_web_search_complete,
    log_web_search_start,
)
from operations.search_locale import searxng_locale_from_messages
from operations.sse_events import owui_citation_event, owui_status_event, url_citation_annotations
from operations.web_search_prompt import prepend_web_search_system
from operations.stream_passthrough import passthrough_vllm_stream


@dataclass(frozen=True)
class SearchContextBudget:
    max_urls: int
    markdown_max_chars: int


_BUDGETS: dict[str, SearchContextBudget] = {
    "low": SearchContextBudget(max_urls=3, markdown_max_chars=6_000),
    "medium": SearchContextBudget(max_urls=5, markdown_max_chars=10_000),
    "high": SearchContextBudget(max_urls=6, markdown_max_chars=16_000),
}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _assistant_text(completion: dict[str, Any]) -> str:
    choices = completion.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else ""


class WebSearchOrchestrator:
    """Run router → search → filter → fetch → final answer."""

    def __init__(
        self,
        *,
        inference: InferencePort,
        mcp: McpToolClient,
        default_model: str,
    ) -> None:
        self._inference = inference
        self._mcp = mcp
        self._default_model = default_model

    def run(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        web_search_tool: dict[str, Any],
        user_location: dict[str, Any],
    ) -> dict[str, Any]:
        """Return OpenAI chat completion dict with content + annotations."""
        model_id = model or self._default_model
        size = str(web_search_tool.get("search_context_size") or "medium").lower()
        budget = _BUDGETS.get(size, _BUDGETS["medium"])
        language = searxng_locale_from_messages(messages)
        pipeline_start = time.perf_counter()

        log_web_search_start(
            search_context_size=size,
            searxng_language=language,
            budget_max_urls=budget.max_urls,
        )

        router = self._router(model_id, messages, language)
        log_router_result(router)
        if router.get("action") == "SKIP":
            duration_ms = (time.perf_counter() - pipeline_start) * 1000
            log_web_search_complete(outcome="skip", pages_fetched=0, duration_ms=duration_ms)
            completion = self._inference.chat_completion(
                {"model": model_id, "messages": messages, "temperature": 0.7},
            )
            content = _assistant_text(completion)
            return self._build_response(model_id, content, [])

        query = str(router.get("query") or "").strip()
        if not query:
            query = self._last_user_text(messages)

        search_payload = self._mcp.call_tool_sync(
            "search_urls",
            {"query": query, "language": language, "max_results": 10},
        )
        hits = search_payload.get("results") or []
        if not hits:
            log_search_no_hits(query=query)
            duration_ms = (time.perf_counter() - pipeline_start) * 1000
            log_web_search_complete(outcome="no_hits", pages_fetched=0, duration_ms=duration_ms)
            completion = self._inference.chat_completion(
                {"model": model_id, "messages": messages, "temperature": 0.7},
            )
            return self._build_response(model_id, _assistant_text(completion), [])

        log_search_hits(query=query, hits=hits)

        urls, fallback_used = self._select_urls(model_id, hits, budget.max_urls)
        log_url_filter_result(selected_urls=urls, fallback_used=fallback_used)

        pages = self._fetch_pages(urls, budget.markdown_max_chars)
        self._log_fetch_outcome(urls, pages)

        final_content = self._final_answer(model_id, messages, query, pages, user_location)
        duration_ms = (time.perf_counter() - pipeline_start) * 1000
        log_web_search_complete(
            outcome="success",
            pages_fetched=len(pages),
            duration_ms=duration_ms,
        )
        annotations = [
            {
                "type": "url_citation",
                "url_citation": {
                    "url": p["url"],
                    "title": p.get("title") or p["url"],
                    "start_index": 0,
                    "end_index": 0,
                },
            }
            for p in pages
        ]
        return self._build_response(model_id, final_content, annotations)

    async def run_stream(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        web_search_tool: dict[str, Any],
        user_location: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        """Orchestrated SSE: OWUI status/citations, then vLLM answer stream."""
        model_id = model or self._default_model
        size = str(web_search_tool.get("search_context_size") or "medium").lower()
        budget = _BUDGETS.get(size, _BUDGETS["medium"])
        language = searxng_locale_from_messages(messages)

        pipeline_start = time.perf_counter()
        log_web_search_start(
            search_context_size=size,
            searxng_language=language,
            budget_max_urls=budget.max_urls,
        )

        yield owui_status_event("Searching the web…", done=False, action="web_search")

        router = await asyncio.to_thread(self._router, model_id, messages, language)
        log_router_result(router)
        if router.get("action") == "SKIP":
            duration_ms = (time.perf_counter() - pipeline_start) * 1000
            log_web_search_complete(outcome="skip", pages_fetched=0, duration_ms=duration_ms)
            yield owui_status_event("Generating answer…", done=False, action="web_search")
            yield owui_status_event("Generating answer…", done=True, action="web_search")
            async for chunk in passthrough_vllm_stream(
                self._inference,
                {"model": model_id, "messages": messages, "temperature": 0.7},
            ):
                yield chunk
            return

        query = str(router.get("query") or "").strip()
        if not query:
            query = self._last_user_text(messages)

        search_payload = await asyncio.to_thread(
            self._mcp.call_tool_sync,
            "search_urls",
            {"query": query, "language": language, "max_results": 10},
        )
        hits = search_payload.get("results") or []
        if not hits:
            log_search_no_hits(query=query)
            duration_ms = (time.perf_counter() - pipeline_start) * 1000
            log_web_search_complete(outcome="no_hits", pages_fetched=0, duration_ms=duration_ms)
            yield owui_status_event("Generating answer…", done=False, action="web_search")
            yield owui_status_event("Generating answer…", done=True, action="web_search")
            async for chunk in passthrough_vllm_stream(
                self._inference,
                {"model": model_id, "messages": messages, "temperature": 0.7},
            ):
                yield chunk
            return

        log_search_hits(query=query, hits=hits)

        yield owui_status_event("Fetching pages…", done=False, action="web_search")

        urls, fallback_used = await asyncio.to_thread(
            self._select_urls,
            model_id,
            hits,
            budget.max_urls,
        )
        log_url_filter_result(selected_urls=urls, fallback_used=fallback_used)

        pages = await asyncio.to_thread(self._fetch_pages, urls, budget.markdown_max_chars)
        self._log_fetch_outcome(urls, pages)
        for page in pages:
            yield owui_citation_event(
                url=page["url"],
                title=page.get("title") or page["url"],
                excerpt=(page.get("markdown") or "")[:500] or None,
            )

        duration_ms = (time.perf_counter() - pipeline_start) * 1000
        log_web_search_complete(
            outcome="success",
            pages_fetched=len(pages),
            duration_ms=duration_ms,
        )

        yield owui_status_event("Generating answer…", done=False, action="web_search")
        yield owui_status_event("Generating answer…", done=True, action="web_search")

        annotations = url_citation_annotations(pages)
        final_body = self._final_stream_body(model_id, messages, query, pages, user_location)
        async for chunk in passthrough_vllm_stream(
            self._inference,
            final_body,
            annotations=annotations if annotations else None,
        ):
            yield chunk

    def _final_stream_body(
        self,
        model: str,
        messages: list[dict[str, Any]],
        query: str,
        pages: list[dict[str, str]],
        user_location: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": self._build_final_messages(messages, user_location, query, pages),
            "temperature": 0.3,
        }

    @staticmethod
    def _build_final_messages(
        messages: list[dict[str, Any]],
        user_location: dict[str, Any],
        query: str,
        pages: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        context = "\n\n---\n\n".join(f"Source: {p['url']}\n{p['markdown']}" for p in pages)
        tool_content = f"Web search results for query {query!r}:\n\n{context}"
        grounded = prepend_web_search_system(messages, user_location)
        return [
            *grounded,
            {
                "role": "tool",
                "content": tool_content,
                "name": "web_search",
            },
        ]

    def _router(
        self,
        model: str,
        messages: list[dict[str, Any]],
        language: str,
    ) -> dict[str, Any]:
        system = (
            "You decide if a web search is needed. Reply with JSON only: "
            '{"action":"SEARCH"|"SKIP","query":"...","language":"'
            + language
            + '"} . Use SEARCH when fresh web facts are required; SKIP otherwise.'
        )
        completion = self._inference.chat_completion(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    *messages,
                ],
                "temperature": 0,
                "max_tokens": 256,
            },
        )
        parsed = _extract_json_object(_assistant_text(completion)) or {}
        if parsed.get("action") not in ("SEARCH", "SKIP"):
            parsed["action"] = "SEARCH"
        if not parsed.get("language"):
            parsed["language"] = language
        return parsed

    def _select_urls(
        self,
        model: str,
        hits: list[dict[str, Any]],
        max_urls: int,
    ) -> tuple[list[str], bool]:
        urls = self._filter_urls(model, hits, max_urls)
        if urls:
            return urls, False
        fallback = [h["url"] for h in hits[:max_urls] if h.get("url")]
        return fallback, True

    @staticmethod
    def _log_fetch_outcome(requested_urls: list[str], pages: list[dict[str, str]]) -> None:
        fetched_urls = [p["url"] for p in pages]
        failed_urls = [u for u in requested_urls if u not in set(fetched_urls)]
        log_fetch_results(
            requested_urls=requested_urls,
            fetched_urls=fetched_urls,
            failed_urls=failed_urls,
        )

    def _filter_urls(self, model: str, hits: list[dict[str, Any]], max_urls: int) -> list[str]:
        snippets = "\n".join(
            f"{i + 1}. {h.get('url')} | {h.get('title', '')} | {h.get('content', '')}"
            for i, h in enumerate(hits)
        )
        prompt = (
            f"Pick up to {max_urls} best URLs for answering the user. "
            f'Return JSON: {{"urls":["https://..."]}} from this list:\n{snippets}'
        )
        completion = self._inference.chat_completion(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 512,
            },
        )
        parsed = _extract_json_object(_assistant_text(completion)) or {}
        urls = parsed.get("urls")
        if isinstance(urls, list):
            return [str(u) for u in urls if u][:max_urls]
        return []

    def _fetch_pages(self, urls: list[str], markdown_max_chars: int) -> list[dict[str, str]]:
        pages: list[dict[str, str]] = []

        def fetch_one(url: str) -> dict[str, str] | None:
            payload = self._mcp.call_tool_sync("fetch_page_markdown", {"url": url})
            md = payload.get("markdown")
            if not isinstance(md, str) or not md.strip():
                return None
            if len(md) > markdown_max_chars:
                md = md[:markdown_max_chars] + "\n…[truncated]"
            return {"url": url, "title": url, "markdown": md}

        with ThreadPoolExecutor(max_workers=min(6, max(1, len(urls)))) as pool:
            futures = {pool.submit(fetch_one, u): u for u in urls}
            for fut in as_completed(futures):
                row = fut.result()
                if row:
                    pages.append(row)
        return pages

    def _final_answer(
        self,
        model: str,
        messages: list[dict[str, Any]],
        query: str,
        pages: list[dict[str, str]],
        user_location: dict[str, Any],
    ) -> str:
        completion = self._inference.chat_completion(
            {
                "model": model,
                "messages": self._build_final_messages(messages, user_location, query, pages),
                "temperature": 0.3,
            },
        )
        return _assistant_text(completion)

    @staticmethod
    def _last_user_text(messages: list[dict[str, Any]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    return " ".join(parts).strip()
        return ""

    @staticmethod
    def _build_response(
        model: str,
        content: str,
        annotations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if annotations:
            message["annotations"] = annotations
        return {
            "id": "chatcmpl-websearch",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "stop",
                },
            ],
        }
