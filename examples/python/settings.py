"""Shared settings for example clients (env vars with sensible defaults)."""

from __future__ import annotations

import json
import os
from typing import Any


def base_url() -> str:
    port = os.environ.get("CHAT_PROXY_PORT", "19000")
    host = os.environ.get("CHAT_PROXY_HOST", "localhost")
    return os.environ.get("CHAT_PROXY_BASE_URL", f"http://{host}:{port}/v1")


def api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "dummy")


def model_id() -> str:
    return os.environ.get("VLLM_SERVED_MODEL", "qwen3-vl-235b-instruct")


def print_json(label: str, obj: Any) -> None:
    """Print full API object as pretty JSON (for debugging / learning the contract)."""
    print(f"=== {label} ===")
    data = obj.model_dump() if hasattr(obj, "model_dump") else obj
    print(json.dumps(data, indent=2, ensure_ascii=False))
