"""Chat-proxy optional API key authentication."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.http_api import create_app
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry


class _FakeInference:
    def list_models(self) -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "test-model"}]}

    def chat_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "ok"}}]}

    def close(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


def _make_app(*, api_key: str = "") -> Any:
    application = create_app()
    settings = ChatProxySettings(api_key=api_key)
    inference = _FakeInference()
    application.state.settings = settings
    application.state.inference = inference
    application.state.chat_service = ChatCompletionService(
        inference,  # type: ignore[arg-type]
        settings,
        build_registry(settings),
    )
    return application


@pytest.fixture
def app_no_auth() -> Any:
    return _make_app()


@pytest.fixture
def app_with_auth() -> Any:
    return _make_app(api_key="secret-key")


@pytest.mark.asyncio
async def test_models_without_auth_when_disabled(app_no_auth) -> None:
    transport = ASGITransport(app=app_no_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "test-model"


@pytest.mark.asyncio
async def test_chat_without_auth_when_disabled(app_no_auth) -> None:
    transport = ASGITransport(app=app_no_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_without_auth_when_enabled(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_models_missing_auth_returns_401(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/models")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_api_key"
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_models_wrong_scheme_returns_401(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/models", headers={"Authorization": "Token secret-key"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_models_wrong_token_returns_401(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/models",
            headers={"Authorization": "Bearer wrong-key"},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_models_valid_bearer_succeeds(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/models",
            headers={"Authorization": "Bearer secret-key"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_valid_bearer_succeeds(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer secret-key"},
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert response.status_code == 200
