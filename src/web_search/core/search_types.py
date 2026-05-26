"""DTOs for SearXNG-backed search (shared by operations and MCP tools)."""

from pydantic import BaseModel, Field


class SearchUrlHit(BaseModel):
    url: str
    title: str | None = None
    content: str | None = None
    engine: str | None = None


class SearchUrlsResult(BaseModel):
    """Stable payload for ``search_urls`` (operations, MCP; success and failure)."""

    ok: bool = True
    code: str | None = None
    message: str | None = None
    query: str
    results: list[SearchUrlHit] = Field(default_factory=list)
