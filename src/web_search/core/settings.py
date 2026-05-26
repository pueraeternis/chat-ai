"""Environment-backed paths and optional overrides for YAML limits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from web_search.core.fetch_policies_config import FetchPoliciesConfig, load_fetch_policies_config
from web_search.core.limits_config import LimitsConfig, load_limits_config


class WebSearchPathsSettings(BaseSettings):
    """KISS: paths and a small set of high-value operational overrides via env."""

    model_config = SettingsConfigDict(
        env_prefix="WEB_SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    limits_file: Path = Field(
        default=Path("config/web_search/default.yaml"),
        description="Path to limits/defaults YAML.",
    )
    fetch_policies_file: Path = Field(
        default=Path("config/web_search/fetch_policies.yaml"),
        description="Path to fetch policy YAML.",
    )

    # Optional overrides (unset = use values from limits YAML).
    searxng_base_url: str | None = Field(
        default=None,
        description="Overrides searxng.base_url in limits file.",
    )
    searxng_request_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Overrides searxng.request_timeout_seconds in limits file.",
    )
    fetch_max_html_bytes: PositiveInt | None = Field(
        default=None,
        description="Overrides fetch.max_html_bytes in limits file.",
    )
    fetch_markdown_max_chars: PositiveInt | None = Field(
        default=None,
        description="Overrides fetch.markdown_max_chars in limits file.",
    )


@dataclass(frozen=True)
class LoadedAppConfig:
    paths: WebSearchPathsSettings
    limits: LimitsConfig
    fetch_policies: FetchPoliciesConfig


def load_app_config(paths: WebSearchPathsSettings | None = None) -> LoadedAppConfig:
    """Load limits and fetch policies from disk, applying optional env overrides."""
    resolved_paths = paths or WebSearchPathsSettings()
    limits = load_limits_config(resolved_paths.limits_file)
    fetch_policies = load_fetch_policies_config(resolved_paths.fetch_policies_file)

    updates: dict = {}
    if resolved_paths.searxng_base_url is not None:
        updates["searxng"] = limits.searxng.model_copy(
            update={"base_url": resolved_paths.searxng_base_url},
        )
    if resolved_paths.searxng_request_timeout_seconds is not None:
        base_s = updates.get("searxng", limits.searxng)
        updates["searxng"] = base_s.model_copy(
            update={"request_timeout_seconds": resolved_paths.searxng_request_timeout_seconds},
        )

    fetch_updates: dict = {}
    if resolved_paths.fetch_max_html_bytes is not None:
        fetch_updates["max_html_bytes"] = resolved_paths.fetch_max_html_bytes
    if resolved_paths.fetch_markdown_max_chars is not None:
        fetch_updates["markdown_max_chars"] = resolved_paths.fetch_markdown_max_chars
    if fetch_updates:
        updates["fetch"] = limits.fetch.model_copy(update=fetch_updates)

    if updates:
        limits = limits.model_copy(update=updates)

    return LoadedAppConfig(paths=resolved_paths, limits=limits, fetch_policies=fetch_policies)
