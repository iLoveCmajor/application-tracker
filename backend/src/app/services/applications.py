"""Creating, reading, editing and deleting applications (FR-1, FR-2, FR-4)."""

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from app.domain import Source, Status
from app.errors import NotFoundError
from app.repositories.base import Repository
from app.repositories.records import ApplicationRecord, StatusEventRecord
from app.services.clock import now, touch

# What PATCH may change. `status` is not here: it changes only through the status endpoint (FR-3).
EDITABLE_FIELDS = frozenset({"company", "role", "link", "source", "applied_date", "follow_up_date", "notes"})


def get_application(repo: Repository, application_id: UUID) -> ApplicationRecord:
    application = repo.get_application(application_id)
    if application is None:
        raise NotFoundError("Application", application_id)
    return application


def list_applications(repo: Repository, status: Status | None = None) -> list[ApplicationRecord]:
    return repo.list_applications(status)


def create_application(
    repo: Repository,
    *,
    company: str,
    role: str,
    source: Source,
    link: str | None = None,
    notes: str | None = None,
) -> ApplicationRecord:
    """A new application at `saved`, with its first history event (FR-4), in one transaction."""
    ts = now()
    application = ApplicationRecord(
        id=uuid4(),
        company=company,
        role=role,
        link=link,
        source=source,
        status=Status.SAVED,
        applied_date=None,
        follow_up_date=None,
        notes=notes,
        created_at=ts,
        updated_at=ts,
    )
    event = StatusEventRecord(
        id=uuid4(),
        application_id=application.id,
        from_status=None,
        to_status=Status.SAVED,
        note=None,
        created_at=ts,
    )
    with repo.transaction():
        repo.save_application(application)
        repo.add_event(event)
    return application


def update_application(repo: Repository, application_id: UUID, changes: dict[str, Any]) -> ApplicationRecord:
    """Applies only the given fields and bumps `updated_at`. Never touches `status`."""
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not editable: {sorted(unknown)}")
    with repo.transaction():
        application = get_application(repo, application_id)
        updated = replace(application, **changes, updated_at=touch(application.updated_at))
        repo.save_application(updated)
    return updated


def delete_application(repo: Repository, application_id: UUID) -> None:
    with repo.transaction():
        get_application(repo, application_id)
        repo.delete_application(application_id)
