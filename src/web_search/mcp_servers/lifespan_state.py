"""Objects shared across MCP requests (FastMCP lifespan context)."""

from dataclasses import dataclass

import httpx

from web_search.adapters.playwright_pool import PlaywrightBrowserPool
from web_search.adapters.searxng_client import SearxngClient
from web_search.core.fetch_policies_config import FetchPoliciesConfig
from web_search.core.limits_config import LimitsConfig
from web_search.core.settings import LoadedAppConfig


@dataclass
class WebSearchLifespanState:
    app_config: LoadedAppConfig
    http_client: httpx.AsyncClient
    playwright_pool: PlaywrightBrowserPool
    searxng_client: SearxngClient
    limits: LimitsConfig
    fetch_policies: FetchPoliciesConfig
