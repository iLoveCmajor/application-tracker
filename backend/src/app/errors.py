"""Domain errors. Each maps to the spec's error format: {"error": {code, message, details}}."""

from typing import Any
from uuid import UUID


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, kind: str, id: UUID) -> None:
        super().__init__(404, "not_found", f"{kind} not found", {"id": str(id)})


class ServiceUnavailableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "service_unavailable", message)
