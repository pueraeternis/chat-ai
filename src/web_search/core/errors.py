"""Application-level errors with stable machine codes for tools and logs."""


class AppError(Exception):
    """Base error carrying a stable ``code`` for API/tool payloads."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class UrlFetchPolicyError(AppError):
    """URL failed fetch policy checks (scheme, host, DNS, IP class)."""


class SearchError(AppError):
    """SearXNG search failed or returned an unusable response."""


class FetchError(AppError):
    """Page fetch via Playwright failed (navigation, transport, unsupported type)."""
