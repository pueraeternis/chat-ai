"""Pydantic models for ``config/default.yaml`` (limits and search defaults)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, PositiveInt


class SearxngLimits(BaseModel):
    base_url: str = Field(
        ...,
        description="SearXNG base URL (e.g. http://searxng:8080).",
    )
    request_timeout_seconds: float = Field(
        ...,
        gt=0,
        description="HTTP client timeout for SearXNG requests.",
    )


class SearchUrlsDefaults(BaseModel):
    max_results: PositiveInt = 10
    max_results_cap: PositiveInt = 50
    categories: str = "general"
    safe_search: int = Field(0, ge=0, le=2)


class PlaywrightLimits(BaseModel):
    navigation_timeout_ms: PositiveInt = 60_000
    max_redirects: PositiveInt = 20
    max_concurrent_contexts: PositiveInt = 4
    context_queue_wait_timeout_seconds: float = Field(120.0, gt=0)


class FetchLimits(BaseModel):
    max_html_bytes: PositiveInt = 2_097_152
    markdown_max_chars: PositiveInt = 200_000


class LimitsConfig(BaseModel):
    searxng: SearxngLimits
    search_urls_defaults: SearchUrlsDefaults
    playwright: PlaywrightLimits
    fetch: FetchLimits


def load_limits_config(path: Path) -> LimitsConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"Limits config must be a mapping at root: {path}"
        raise TypeError(msg)
    return LimitsConfig.model_validate(raw)
