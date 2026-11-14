"""The storage interface the services depend on.

`SqlRepository` (repositories/sql.py) implements it with SQLAlchemy. Services
depend only on this protocol, never on SQLAlchemy.
"""

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from app.domain import Status
from app.repositories.records import ApplicationRecord, StatusEventRecord


class Repository(Protocol):
    def transaction(self) -> AbstractContextManager[None]:
        """All writes inside commit together or not at all. Nested calls join the outer one."""
        ...

    # Applications
    def list_applications(self, status: Status | None = None) -> list[ApplicationRecord]:
        """Newest `updated_at` first, optionally only those with `status`."""
        ...

    def get_application(self, application_id: UUID) -> ApplicationRecord | None: ...

    def save_application(self, application: ApplicationRecord) -> None:
        """Insert or update by id."""
        ...

    def delete_application(self, application_id: UUID) -> None:
        """Also deletes the application's status events."""
        ...

    # Status events
    def add_event(self, event: StatusEventRecord) -> None: ...

    def list_events(self, application_id: UUID) -> list[StatusEventRecord]:
        """Oldest first."""
        ...
