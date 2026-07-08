"""Map application errors to OpenAI-style HTTP JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import Request

from core.errors import AppError, ValidationError


def openai_error_payload(
    message: str,
    *,
    code: str = "invalid_request_error",
    param: str | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"message": message, "type": "invalid_request_error", "code": code}
    if param is not None:
        err["param"] = param
    return {"error": err}


def unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=openai_error_payload(
            "Incorrect API key provided",
            code="invalid_api_key",
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


def validation_response(exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=openai_error_payload(exc.message, code=exc.code, param=exc.param),
    )


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    status = 400 if isinstance(exc, ValidationError) else 502
    code = exc.code if isinstance(exc, ValidationError) else "server_error"
    if isinstance(exc, ValidationError):
        return validation_response(exc)
    return JSONResponse(
        status_code=status,
        content={"error": {"message": exc.message, "type": "server_error", "code": code}},
    )
