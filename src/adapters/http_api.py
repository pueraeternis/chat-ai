"""FastAPI OpenAI-compatible HTTP surface."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from adapters.vllm_inference import VllmInferenceAdapter
from core.errors import AppError, ValidationError
from core.log_events import (
    log_request_end,
    log_request_start,
    log_validation_error,
    resolve_request_mode,
)
from core.logging_config import configure_logging
from core.openai_errors import app_error_handler, openai_error_payload
from core.request_context import new_request_id, reset_request_id, set_request_id
from core.settings import ChatProxySettings
from operations.chat_completion import ChatCompletionService, build_registry

_STARTUP_LOGGER = logging.getLogger("chat_proxy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = ChatProxySettings()
    configure_logging(settings)
    inference = VllmInferenceAdapter(settings)
    registry = build_registry(settings)
    app.state.settings = settings
    app.state.inference = inference
    app.state.chat_service = ChatCompletionService(inference, settings, registry)
    _STARTUP_LOGGER.info(
        "startup",
        extra={
            "bind": f"{settings.host}:{settings.port}",
            "default_model": settings.default_model,
            "web_search_mcp_url": settings.web_search_mcp_url,
        },
    )
    yield
    inference.close()
    await inference.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="chat-proxy", lifespan=lifespan)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ValidationError, _validation_error_handler)

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
        return await _handle_chat_completion(request, body)

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


async def _validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ValidationError):
        log_validation_error(code=exc.code, param=exc.param)
    return await app_error_handler(_request, exc)


async def _handle_chat_completion(
    request: Request,
    body: dict[str, Any],
) -> dict[str, Any] | JSONResponse | StreamingResponse:
    request_id = new_request_id()
    token = set_request_id(request_id)
    mode = resolve_request_mode(body)
    started = time.perf_counter()
    log_request_start(body)

    service: ChatCompletionService = request.app.state.chat_service
    is_stream = bool(body.get("stream"))
    try:
        if is_stream:
            # request_id is re-bound inside the stream generator (Starlette runs it
            # in a different task); reset the handler token before returning.
            reset_request_id(token)
            return StreamingResponse(
                _stream_with_logging(
                    service,
                    body,
                    request,
                    request_id=request_id,
                    mode=mode,
                    started=started,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        result = service.handle(body)
    except Exception:
        if not is_stream:
            log_request_end(
                mode=mode,
                status="error",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        raise
    else:
        log_request_end(mode=mode, status="ok", duration_ms=(time.perf_counter() - started) * 1000)
        return result
    finally:
        if not is_stream:
            reset_request_id(token)


async def _stream_with_logging(
    service: ChatCompletionService,
    body: dict[str, Any],
    request: Request,
    *,
    request_id: str,
    mode: str,
    started: float,
) -> AsyncIterator[bytes]:
    stream_token = set_request_id(request_id)
    status = "ok"
    try:
        async for chunk in _stream_with_disconnect(service, body, request):
            yield chunk
    except Exception:
        status = "error"
        raise
    finally:
        log_request_end(
            mode=mode,
            status=status,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        reset_request_id(stream_token)


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
    configure_logging(settings)
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
