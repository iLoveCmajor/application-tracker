"""Turn every failure into the spec's error body: {"error": {code, message, details}}."""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AppError

logger = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _field_name(loc: Sequence[int | str]) -> str:
    names = [str(part) for part in loc if isinstance(part, str) and part not in ("body", "query", "path")]
    return names[-1] if names else "body"


def _describe(error: dict[str, Any]) -> str:
    """A short message the UI can show as is, e.g. "Name must not be empty"."""
    field = _field_name(error.get("loc", ()))
    label = field.replace("_", " ").capitalize()
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    if kind == "json_invalid":
        return "Request body is not valid JSON"
    if kind == "missing":
        return f"{label} is required"
    if "input" in error and error["input"] is None:
        return f"{label} must not be null"
    if kind == "string_too_short":
        return f"{label} must not be empty"
    if kind == "string_too_long":
        return f"{label} must be at most {ctx.get('max_length'):,} characters"
    if kind == "string_pattern_mismatch" and field == "link":
        return "Link must start with http:// or https://"
    if kind == "enum":
        return f"{label} must be one of: {ctx.get('expected', '')}"
    if kind == "extra_forbidden":
        return f"Unknown field '{field}'"
    if kind.startswith("date"):
        return f"{label} must be a date (YYYY-MM-DD)"
    if kind.startswith("int"):
        return f"{label} must be an integer"
    if kind.startswith("uuid"):
        return f"{label} must be a UUID"
    return f"{label}: {error.get('msg', 'is invalid')}"


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status, exc.code, exc.message, exc.details)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = list(exc.errors())
    # A malformed id in the URL can't match any resource, so report it as missing.
    if errors and all(e.get("loc", ())[:1] == ("path",) for e in errors):
        return error_response(404, "not_found", "Not found", {"id": str(errors[0].get("input"))})
    first = errors[0] if errors else {}
    return error_response(
        422,
        "validation_error",
        _describe(first),
        {
            "field": _field_name(first.get("loc", ())),
            "errors": [
                {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")} for e in errors
            ],
        },
    )


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return error_response(404, "not_found", "Not found")
    code = "internal_error" if exc.status_code >= 500 else "validation_error"
    return error_response(exc.status_code, code, str(exc.detail))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "internal_error", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
