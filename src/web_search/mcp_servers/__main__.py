"""CLI entry for the MCP web-search service."""

from __future__ import annotations

import argparse

from web_search.mcp_servers.factory import create_web_search_mcp
from web_search.mcp_servers.http_asgi import main as http_main


def main() -> None:
    parser = argparse.ArgumentParser(description="web-search-mcp")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run MCP over stdio (local dev; production uses streamable HTTP).",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run MCP streamable HTTP via uvicorn (bind WEB_SEARCH_HOST / WEB_SEARCH_PORT).",
    )
    args = parser.parse_args()
    if args.http:
        http_main()
        return
    if args.stdio:
        create_web_search_mcp().run(transport="stdio")
        return
    print(
        "web-search-mcp: use --stdio for local MCP, --http for streamable HTTP, "
        "or `uv run web-search-mcp-http`. See README.md and docs/plans/01-web-search-mcp.md.",
    )


if __name__ == "__main__":
    main()
