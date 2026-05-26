"""FastAPI OpenAI-compatible HTTP surface."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from adapters.vllm_inference import VllmInferenceAdapter
from core.errors import AppError
from core.openai_errors import app_error_handler, openai_error_payload
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = ChatProxySettings()
    inference = VllmInferenceAdapter(settings)
    registry = build_registry(settings)
    app.state.settings = settings
    app.state.inference = inference
    app.state.chat_service = ChatCompletionService(inference, settings, registry)
    yield
    inference.close()
    await inference.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="chat-proxy", lifespan=lifespan)
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "chat-proxy"}

    @app.get("/v1/models")
    async def list_models(request: Request) -> dict[str, Any]:
        inference: VllmInferenceAdapter = request.app.state.inference
        return inference.list_models()

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        request: Request,
    ) -> dict[str, Any] | JSONResponse | StreamingResponse:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content=openai_error_payload("Request body must be a JSON object"),
            )
        service: ChatCompletionService = request.app.state.chat_service
        if body.get("stream"):
            return StreamingResponse(
                _stream_with_disconnect(service, body, request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        return service.handle(body)

    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def v1_not_implemented(path: str) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=openai_error_payload(
                f"Endpoint /v1/{path} is not implemented",
                code="not_found",
            ),
        )

    return app


async def _stream_with_disconnect(
    service: ChatCompletionService,
    body: dict[str, Any],
    request: Request,
):
    gen = service.stream(body)
    try:
        async for chunk in gen:
            if await request.is_disconnected():
                await gen.aclose()
                return
            yield chunk
    finally:
        await gen.aclose()


def main() -> None:
    settings = ChatProxySettings()
    host = settings.host
    port = settings.port
    uvicorn.run(
        "adapters.http_api:create_app",
        host=host,
        port=port,
        factory=True,
    )


if __name__ == "__main__":
    main()
