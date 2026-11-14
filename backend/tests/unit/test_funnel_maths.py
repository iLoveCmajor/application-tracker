"""AC-5.1, AC-5.2: the funnel maths as pure functions (no database)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain import Source, Status
from app.repositories.records import ApplicationRecord, StatusEventRecord
from app.services.funnel import SourceFunnel, compute_funnel, reached_applied, reached_screen, screen_rate

S = Status
T0 = datetime(2026, 3, 1, tzinfo=UTC)


def history(source: Source, *path: Status) -> tuple[ApplicationRecord, list[StatusEventRecord]]:
    """An application at the end of `path`, with one event per step (the first is the create event)."""
    app = ApplicationRecord(
        id=uuid4(),
        company="Northwind Analytics",
        role="ML Engineer",
        link=None,
        source=source,
        status=path[-1],
        applied_date=None,
        follow_up_date=None,
        notes=None,
        created_at=T0,
        updated_at=T0,
    )
    events = [
        StatusEventRecord(
            id=uuid4(),
            application_id=app.id,
            from_status=path[i - 1] if i else None,
            to_status=status,
            note=None,
            created_at=T0 + timedelta(days=i),
        )
        for i, status in enumerate(path)
    ]
    return app, events


def funnel_of(*histories: tuple[ApplicationRecord, list[StatusEventRecord]]) -> dict[Source, SourceFunnel]:
    funnel = compute_funnel([a for a, _ in histories], [e for _, es in histories for e in es])
    return {row.source: row for row in funnel.by_source}


# ---- AC-5.1 reached a stage -------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "applied", "screen"),
    [
        ((S.SAVED, S.APPLIED, S.SCREEN, S.REJECTED), True, True),
        ((S.SAVED, S.REJECTED), False, False),
        ((S.SAVED, S.INTERVIEW), True, True),
        ((S.SAVED, S.APPLIED, S.SAVED), True, False),
        ((S.SAVED, S.APPLIED, S.GHOSTED), True, False),
        ((S.SAVED,), False, False),
        ((S.SAVED, S.OFFER), True, True),
        ((S.SAVED, S.GHOSTED, S.REJECTED, S.SAVED), False, False),
        ((S.SAVED, S.APPLIED, S.REJECTED, S.SCREEN), True, True),
    ],
)
def test_ac5_1_reached_a_stage(path: tuple[Status, ...], applied: bool, screen: bool) -> None:
    assert reached_applied(path) is applied
    assert reached_screen(path) is screen
    row = funnel_of(history(Source.COLD, *path))[Source.COLD]
    assert (row.applied, row.reached_screen) == (int(applied), int(screen))


def test_ac5_1_counts_come_from_events_not_current_status() -> None:
    app, events = history(Source.REFERRAL, S.SAVED, S.SCREEN, S.REJECTED)
    funnel = compute_funnel([app], events)
    assert funnel.by_status[S.REJECTED] == 1
    assert funnel.by_source[2] == SourceFunnel(Source.REFERRAL, 1, 1, 1.0)


def test_ac5_1_events_of_unknown_applications_are_ignored() -> None:
    _, orphan_events = history(Source.COLD, S.SAVED, S.APPLIED, S.SCREEN)
    app, events = history(Source.COLD, S.SAVED)
    funnel = compute_funnel([app], events + orphan_events)
    assert funnel.total == 1
    assert funnel.by_source[0] == SourceFunnel(Source.COLD, 0, 0, None)


def test_ac5_1_counts_per_status_and_source() -> None:
    histories = [
        history(Source.COLD, S.SAVED, S.APPLIED),
        history(Source.COLD, S.SAVED, S.APPLIED, S.SCREEN),
        history(Source.COLD, S.SAVED, S.APPLIED, S.GHOSTED),
        history(Source.INBOUND, S.SAVED),
        history(Source.INBOUND, S.SAVED, S.INTERVIEW, S.OFFER),
    ]
    funnel = compute_funnel([a for a, _ in histories], [e for _, es in histories for e in es])
    assert funnel.total == 5
    assert funnel.by_status == {
        S.SAVED: 1,
        S.APPLIED: 1,
        S.SCREEN: 1,
        S.INTERVIEW: 0,
        S.OFFER: 1,
        S.REJECTED: 0,
        S.GHOSTED: 1,
    }
    assert funnel.by_source == [
        SourceFunnel(Source.COLD, 3, 1, 0.333),
        SourceFunnel(Source.INBOUND, 1, 1, 1.0),
        SourceFunnel(Source.REFERRAL, 0, 0, None),
    ]


def test_ac5_1_empty() -> None:
    funnel = compute_funnel([], [])
    assert funnel.total == 0
    assert funnel.by_status == dict.fromkeys(Status, 0)
    assert [(r.source, r.applied, r.reached_screen, r.screen_rate) for r in funnel.by_source] == [
        (Source.COLD, 0, 0, None),
        (Source.INBOUND, 0, 0, None),
        (Source.REFERRAL, 0, 0, None),
    ]


# ---- AC-5.2 screen rate -----------------------------------------------------------


@pytest.mark.parametrize(
    ("screened", "applied", "rate"),
    [
        (1, 3, 0.333),
        (2, 3, 0.667),
        (0, 5, 0.0),
        (4, 4, 1.0),
        (1, 8, 0.125),
        (1, 6, 0.167),
        (1, 7, 0.143),
        (1, 2000, 0.001),  # 0.0005 rounds half up
        (1, 2001, 0.0),
    ],
)
def test_ac5_2_screen_rate_rounds_to_3_decimals(screened: int, applied: int, rate: float) -> None:
    assert screen_rate(screened, applied) == rate


def test_ac5_2_screen_rate_is_none_when_nothing_was_applied() -> None:
    assert screen_rate(0, 0) is None


def test_deliberately_broken() -> None:
    assert 1 + 1 == 3
