"""Result DTOs for Playwright-backed page fetch (operations and MCP)."""

from pydantic import BaseModel


class FetchPageHtmlResult(BaseModel):
    ok: bool = True
    code: str | None = None
    message: str | None = None
    url: str
    final_url: str | None = None
    content_type: str | None = None
    html: str | None = None
    truncated: bool = False
    html_byte_length_original: int | None = None
    html_byte_length_returned: int | None = None


class FetchPageMarkdownResult(BaseModel):
    ok: bool = True
    code: str | None = None
    message: str | None = None
    url: str
    final_url: str | None = None
    content_type: str | None = None
    markdown: str | None = None
    markdown_truncated: bool = False
    markdown_char_length_original: int | None = None
    markdown_char_length_returned: int | None = None
