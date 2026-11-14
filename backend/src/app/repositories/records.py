"""Stored rows, matching the tables in _docs/specs.md."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain import Source, Status


@dataclass
class ApplicationRecord:
    id: UUID
    company: str
    role: str
    link: str | None
    source: Source
    status: Status
    applied_date: date | None
    follow_up_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class StatusEventRecord:
    id: UUID
    application_id: UUID
    from_status: Status | None
    to_status: Status
    note: str | None
    created_at: datetime
