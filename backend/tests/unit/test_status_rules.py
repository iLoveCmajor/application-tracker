"""AC-3.1: the date rules and the same-status check, as pure functions (no database, no clock)."""

from datetime import date

import pytest

from app.domain import Status
from app.errors import InvalidTransitionError
from app.services.status_rules import check_transition, dates_after_change

TODAY = date(2026, 3, 10)
EARLIER = date(2026, 2, 1)
FOLLOW_UP = date(2026, 2, 8)


def test_ac3_1_to_applied_with_empty_applied_date_sets_both() -> None:
    assert dates_after_change(Status.APPLIED, None, None, TODAY) == (TODAY, date(2026, 3, 17))


def test_ac3_1_to_applied_keeps_applied_date_and_resets_follow_up() -> None:
    assert dates_after_change(Status.APPLIED, EARLIER, FOLLOW_UP, TODAY) == (EARLIER, date(2026, 3, 17))


def test_ac3_1_follow_up_crosses_month_and_year_ends() -> None:
    assert dates_after_change(Status.APPLIED, None, None, date(2026, 12, 28)) == (
        date(2026, 12, 28),
        date(2027, 1, 4),
    )


@pytest.mark.parametrize("new", [Status.OFFER, Status.REJECTED, Status.GHOSTED])
def test_ac3_1_closing_statuses_keep_applied_date_and_clear_follow_up(new: Status) -> None:
    assert dates_after_change(new, EARLIER, FOLLOW_UP, TODAY) == (EARLIER, None)
    assert dates_after_change(new, None, None, TODAY) == (None, None)


@pytest.mark.parametrize("new", [Status.SAVED, Status.SCREEN, Status.INTERVIEW])
def test_ac3_1_other_statuses_keep_both_dates(new: Status) -> None:
    assert dates_after_change(new, EARLIER, FOLLOW_UP, TODAY) == (EARLIER, FOLLOW_UP)
    assert dates_after_change(new, None, None, TODAY) == (None, None)


@pytest.mark.parametrize("status", list(Status))
def test_ac3_1_moving_to_the_current_status_is_refused(status: Status) -> None:
    with pytest.raises(InvalidTransitionError) as raised:
        check_transition(status, status)
    assert raised.value.status == 409
    assert raised.value.code == "invalid_transition"
    assert raised.value.details == {"status": status.value}


@pytest.mark.parametrize("current", list(Status))
@pytest.mark.parametrize("new", list(Status))
def test_ac3_1_any_status_may_move_to_any_other(current: Status, new: Status) -> None:
    if current != new:
        check_transition(current, new)
