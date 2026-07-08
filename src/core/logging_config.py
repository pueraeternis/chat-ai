"""Logging setup for chat-proxy."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from core.log_events import _LOG_RECORD_SKIP
from core.request_context import get_request_id
from core.settings import ChatProxySettings


class RequestContextFilter(logging.Filter):
    """Attach request_id from context when not already on the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            rid = get_request_id()
            if rid:
                record.request_id = rid
        return True


class StructuredTextFormatter(logging.Formatter):
    """Human-readable single line with key=value fields."""

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            record.levelname,
            record.name,
        ]
        rid = getattr(record, "request_id", None)
        if rid:
            parts.append(f"request_id={rid}")
        parts.append(record.getMessage())
        for key in sorted(record.__dict__):
            if key in _LOG_RECORD_SKIP or key == "request_id":
                continue
            value = record.__dict__[key]
            if value is None:
                continue
            parts.append(f"{key}={_format_field(value)}")
        return " ".join(parts)


class JsonLogFormatter(logging.Formatter):
    """One JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        for key in sorted(record.__dict__):
            if key in _LOG_RECORD_SKIP or key == "request_id":
                continue
            value = record.__dict__[key]
            if value is None:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def _format_field(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def configure_logging(settings: ChatProxySettings) -> None:
    """Configure root chat_proxy loggers and uvicorn levels."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if settings.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(StructuredTextFormatter())

    for name in (
        "chat_proxy",
        "chat_proxy.http",
        "chat_proxy.routing",
        "chat_proxy.web_search",
        "chat_proxy.upstream",
    ):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.setLevel(level)
