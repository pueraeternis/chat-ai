"""Per-request context for structured logging."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    """Generate a new correlation id."""
    return str(uuid4())


def get_request_id() -> str | None:
    """Current request id, if set."""
    return _request_id.get()


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind request_id for the current context; returns reset token."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore previous request_id after a scoped block."""
    _request_id.reset(token)
