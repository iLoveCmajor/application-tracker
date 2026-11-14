"""Business rules for a status change (spec: "Statuses", "Dates on a status change").

Pure functions: no database, no clock. The caller passes `today`.
"""

from datetime import date, timedelta

from app.domain import Status
from app.errors import InvalidTransitionError

FOLLOW_UP_DAYS = 7

# Moving to one of these clears follow_up_date (FR-6).
CLOSING_STATUSES = frozenset({Status.OFFER, Status.REJECTED, Status.GHOSTED})


def check_transition(current: Status, new: Status) -> None:
    """Any status may move to any other; moving to the current one is refused."""
    if current == new:
        raise InvalidTransitionError(current)


def dates_after_change(
    new: Status, applied_date: date | None, follow_up_date: date | None, today: date
) -> tuple[date | None, date | None]:
    """(applied_date, follow_up_date) after moving to `new` (FR-5, FR-6)."""
    if new == Status.APPLIED:
        return applied_date or today, today + timedelta(days=FOLLOW_UP_DAYS)
    if new in CLOSING_STATUSES:
        return applied_date, None
    return applied_date, follow_up_date
