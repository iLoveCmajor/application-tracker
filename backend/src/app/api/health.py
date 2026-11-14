"""Liveness and readiness, outside the /api/v1 prefix (FR-10)."""

from fastapi import APIRouter, Request

from app import schemas
from app.config import app_version
from app.db.engine import is_reachable
from app.errors import ServiceUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health", operation_id="health", summary="Liveness check")
def health() -> schemas.Health:
    return schemas.Health(status="ok", version=app_version())


@router.get(
    "/ready",
    operation_id="ready",
    summary="Readiness check",
    responses={503: {"description": "The database does not answer"}},
)
def ready(request: Request) -> schemas.Ready:
    if not is_reachable(request.app.state.engine):
        raise ServiceUnavailableError("Database is not reachable")
    return schemas.Ready(status="ok")
