"""Smoke: HTTP ASGI app exposes MCP and health routes (no lifespan / browser)."""

from web_search.mcp_servers.http_asgi import build_http_app


def test_http_app_routes_include_health_and_mcp() -> None:
    app = build_http_app()
    paths = [getattr(r, "path", None) for r in app.router.routes]
    assert "/health" in paths
    assert "/mcp" in paths
