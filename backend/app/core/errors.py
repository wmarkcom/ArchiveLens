from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def app_error_handler(request: Request, exc: AppError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> ORJSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    return ORJSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, str(exc.detail)),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "请求参数校验失败", {"errors": exc.errors()}),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
