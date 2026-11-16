"""JSON logs with a request id (spec: "Stack and operations", Logs; FR-10).

Every log line is one JSON object on stdout. Each HTTP request logs one line with its method, path
(no query string), status, duration and request id. The id comes from the `X-Request-ID` header,
or is generated, and is returned in that header. Request bodies and application fields are never
logged: the request line is built from the method, the path and the status only.

When a span is current (telemetry on, #29), every line also carries its `trace_id` and `span_id`, so
a log line can be matched to its trace. With telemetry off there is no span and the fields are absent.
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_response

REQUEST_ID_HEADER = "X-Request-ID"
DEFAULT_LEVEL = "INFO"

# An incoming id is echoed only if it looks like an id; anything else gets a generated one.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:/+=-]{1,128}$")
# Fields a log call may add with `extra=`; nothing else from a record reaches the output.
_EXTRA_FIELDS = ("method", "path", "status", "duration_ms")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("app.request")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            entry["trace_id"] = trace.format_trace_id(span_context.trace_id)
            entry["span_id"] = trace.format_span_id(span_context.span_id)
        for field in _EXTRA_FIELDS:
            if field in record.__dict__:
                entry[field] = record.__dict__[field]
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever `sys.stdout` is at the time, so a replaced stdout (tests) still works."""

    _app_json = True

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def log_level() -> str:
    """LOG_LEVEL (any case): DEBUG, INFO, WARNING, ERROR or CRITICAL. Unset or unknown: INFO."""
    value = os.environ.get("LOG_LEVEL", "").strip().upper()
    return value if value in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else DEFAULT_LEVEL


def configure_logging(level: str | None = None) -> None:
    """Send every logger, uvicorn's included, through one JSON handler on stdout.

    Safe to call more than once: it replaces the handler it installed before. uvicorn's access log
    is turned off because the request middleware below writes the request lines.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_json", False):
            root.removeHandler(handler)
    handler = _StdoutHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level or log_level())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(logging.NOTSET)
    logging.getLogger("uvicorn.access").disabled = True
    # SQLAlchemy logs statements with their parameters (application fields) at INFO: never let it.
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            candidate = value.decode("latin-1").strip()
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


class RequestLogMiddleware:
    """Sets the request id, returns it in `X-Request-ID`, and logs one line per request.

    An unhandled exception is logged here once, at ERROR with the traceback in the log line only,
    and answered with the spec's `internal_error` body, so the server never logs it a second time.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        def fields() -> dict[str, Any]:
            return {
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }

        try:
            try:
                await self.app(scope, receive, send_with_id)
            except Exception:
                status = 500
                logger.exception(
                    "%s %s failed with an unhandled error", scope["method"], scope["path"], extra=fields()
                )
                if response_started:
                    raise
                response = error_response(500, "internal_error", "Internal server error")
                await response(scope, receive, send_with_id)
                return
            level = logging.WARNING if status >= 500 else logging.INFO
            logger.log(level, "%s %s %d", scope["method"], scope["path"], status, extra=fields())
        finally:
            request_id_var.reset(token)
