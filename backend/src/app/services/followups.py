"""Applications due a follow-up (FR-7, spec "Follow-ups")."""

from collections.abc import Iterable
from datetime import date

from app.domain import Status
from app.repositories.base import Repository
from app.repositories.records import ApplicationRecord

# Still in play: waiting on the company, so worth chasing.
OPEN_STATUSES = frozenset({Status.APPLIED, Status.SCREEN, Status.INTERVIEW})


def is_due(status: Status, follow_up_date: date | None, today: date) -> bool:
    """Pure: the follow-up date is today or earlier and the status is still open."""
    return status in OPEN_STATUSES and follow_up_date is not None and follow_up_date <= today


def due_followups(applications: Iterable[ApplicationRecord], today: date) -> list[ApplicationRecord]:
    """Pure: the due ones, by follow_up_date ascending, then company (then id, so ties are stable)."""
    due = [a for a in applications if is_due(a.status, a.follow_up_date, today)]
    return sorted(due, key=lambda a: (a.follow_up_date, a.company, str(a.id)))


def list_followups(repo: Repository, today: date) -> list[ApplicationRecord]:
    return due_followups(repo.list_applications(), today)
