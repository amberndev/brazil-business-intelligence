from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_body(code: str, message: str, status: int) -> dict:
    return {"error": {"code": code, "message": message, "status": status}}


def error_response(code: str, message: str, status: int, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=error_body(code, message, status),
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    headers = getattr(exc, "headers", None) or {}
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": detail},
            headers=headers or None,
        )
    return error_response("internal_error", str(detail), exc.status_code, headers or None)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response("validation_error", "Request validation failed.", 422)
