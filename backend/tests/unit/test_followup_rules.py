"""AC-4.1: "is due" as a pure function of status, follow_up_date and today; AC-4.4 ordering."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain import Source, Status
from app.repositories.records import ApplicationRecord
from app.services.followups import due_followups, is_due

TODAY = date(2026, 3, 10)
PAST = date(2026, 3, 1)


@pytest.mark.parametrize("status", [Status.APPLIED, Status.SCREEN, Status.INTERVIEW])
def test_ac4_1_open_statuses_with_past_date_are_due(status: Status) -> None:
    assert is_due(status, PAST, TODAY)


def test_ac4_1_date_equal_to_today_is_due() -> None:
    assert is_due(Status.APPLIED, TODAY, TODAY)


def test_ac4_1_date_before_today_is_due() -> None:
    assert is_due(Status.APPLIED, TODAY - timedelta(days=1), TODAY)


def test_ac4_1_tomorrow_is_not_due() -> None:
    assert not is_due(Status.APPLIED, TODAY + timedelta(days=1), TODAY)


@pytest.mark.parametrize("status", list(Status))
def test_ac4_1_null_date_is_never_due(status: Status) -> None:
    assert not is_due(status, None, TODAY)


@pytest.mark.parametrize("status", [Status.SAVED, Status.OFFER, Status.REJECTED, Status.GHOSTED])
def test_ac4_1_closed_or_unsent_statuses_are_not_due(status: Status) -> None:
    assert not is_due(status, PAST, TODAY)
    assert not is_due(status, TODAY, TODAY)


def record(company: str, follow_up: date | None, status: Status = Status.APPLIED) -> ApplicationRecord:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    return ApplicationRecord(
        id=uuid4(),
        company=company,
        role="Data Engineer",
        link=None,
        source=Source.COLD,
        status=status,
        applied_date=None,
        follow_up_date=follow_up,
        notes=None,
        created_at=ts,
        updated_at=ts,
    )


def test_ac4_4_due_list_is_by_date_then_company() -> None:
    apps = [
        record("Gamma Systems", TODAY),
        record("Beta Works", PAST),
        record("Alpha Labs", TODAY),
        record("Delta Freight", PAST, Status.REJECTED),
        record("Epsilon Health", TODAY + timedelta(days=1)),
        record("Zeta Retail", None),
        record("Alpha Labs", date(2026, 2, 20), Status.INTERVIEW),
    ]
    due = due_followups(apps, TODAY)
    assert [(a.company, a.follow_up_date) for a in due] == [
        ("Alpha Labs", date(2026, 2, 20)),
        ("Beta Works", PAST),
        ("Alpha Labs", TODAY),
        ("Gamma Systems", TODAY),
    ]


def test_ac4_5_nothing_due_is_empty() -> None:
    assert due_followups([], TODAY) == []
    assert due_followups([record("Beta Works", TODAY + timedelta(days=1))], TODAY) == []
