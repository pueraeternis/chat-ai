"""Environment-backed settings for chat-proxy."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Container default: listen on all interfaces. Override with CHAT_PROXY_HOST (e.g. localhost for local dev).
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_VLLM_CONNECT_TIMEOUT_SECONDS = 10.0


class ChatProxySettings(BaseSettings):
    """Proxy service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CHAT_PROXY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default=DEFAULT_BIND_HOST, description="Bind host.")
    port: int = Field(default=8080, ge=1, le=65535, description="Bind port.")
    vllm_base_url: str = Field(
        default="http://vllm:8000/v1",
        description="vLLM OpenAI API base URL.",
    )
    vllm_timeout_seconds: float = Field(default=600.0, gt=0)
    vllm_connect_timeout_seconds: float = Field(
        default=DEFAULT_VLLM_CONNECT_TIMEOUT_SECONDS,
        gt=0,
    )
    default_model: str = Field(default="qwen3-vl-30b-instruct")
    web_search_mcp_url: str = Field(
        default="http://web-search-mcp:3333/mcp",
        description="Streamable HTTP MCP endpoint for web-search.",
    )
    mcp_timeout_seconds: float = Field(default=180.0, gt=0)
    api_key: str = Field(
        default="",
        description="Optional static API key. When set, /v1/models and /v1/chat/completions require Authorization: Bearer.",
    )
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, …).")
    log_json: bool = Field(default=False, description="Emit JSON log lines when true.")
