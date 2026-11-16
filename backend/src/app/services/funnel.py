"""Funnel numbers (FR-8, spec "Reached a stage" and "Funnel").

Everything but `get_funnel` is pure: no database, no clock.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.domain import Source, Status
from app.repositories.base import Repository
from app.repositories.records import ApplicationRecord, StatusEventRecord

# Rejected and ghosted are outcomes, not stages, so they count only through the stages before them.
APPLIED_OR_LATER = frozenset({Status.APPLIED, Status.SCREEN, Status.INTERVIEW, Status.OFFER})
SCREEN_OR_LATER = frozenset({Status.SCREEN, Status.INTERVIEW, Status.OFFER})


@dataclass(frozen=True)
class SourceFunnel:
    source: Source
    applied: int
    reached_screen: int
    screen_rate: float | None


@dataclass(frozen=True)
class Funnel:
    total: int
    by_status: dict[Status, int]
    by_source: list[SourceFunnel]


def reached_applied(to_statuses: Iterable[Status]) -> bool:
    return any(s in APPLIED_OR_LATER for s in to_statuses)


def reached_screen(to_statuses: Iterable[Status]) -> bool:
    return any(s in SCREEN_OR_LATER for s in to_statuses)


def screen_rate(reached_screen: int, applied: int) -> float | None:
    """`reached_screen / applied` rounded half up to 3 decimals; None when nothing was applied."""
    if applied == 0:
        return None
    rate = (Decimal(reached_screen) / Decimal(applied)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return float(rate)


def compute_funnel(applications: Iterable[ApplicationRecord], events: Iterable[StatusEventRecord]) -> Funnel:
    """Counts per current status, and per source how far applications got by their events.

    Events of applications not in `applications` (deleted ones) are ignored.
    """
    apps = list(applications)
    history: dict[UUID, list[Status]] = {a.id: [] for a in apps}
    for event in events:
        if event.application_id in history:
            history[event.application_id].append(event.to_status)

    by_status = dict.fromkeys(Status, 0)
    applied = dict.fromkeys(Source, 0)
    screened = dict.fromkeys(Source, 0)
    for app in apps:
        by_status[app.status] += 1
        if reached_applied(history[app.id]):
            applied[app.source] += 1
        if reached_screen(history[app.id]):
            screened[app.source] += 1

    return Funnel(
        total=len(apps),
        by_status=by_status,
        by_source=[
            SourceFunnel(
                source, applied[source], screened[source], screen_rate(screened[source], applied[source])
            )
            for source in Source
        ],
    )


def get_funnel(repo: Repository) -> Funnel:
    with repo.transaction():  # one snapshot of both tables
        return compute_funnel(repo.list_applications(), repo.list_all_events())
