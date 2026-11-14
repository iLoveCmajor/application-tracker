"""AC-8.7, AC-8.10: demo data seeds an empty database once, through the status rules."""

from datetime import date

from fastapi.testclient import TestClient
from helpers import API, create_application
from sqlalchemy import Engine

from app.domain import Source, Status
from app.main import create_app
from app.repositories.sql import SqlRepository
from app.services.followups import list_followups
from app.services.seed import seed_if_empty

TODAY = date(2026, 3, 10)


def test_ac8_10_seeds_an_empty_database_once(repo: SqlRepository) -> None:
    created = seed_if_empty(repo, TODAY)
    assert 8 <= created <= 12
    assert len(repo.list_applications()) == created

    assert seed_if_empty(repo, TODAY) == 0
    assert len(repo.list_applications()) == created


def test_ac8_10_seeds_nothing_when_an_application_exists(client: TestClient, repo: SqlRepository) -> None:
    create_application(client)
    assert seed_if_empty(repo, TODAY) == 0
    assert len(repo.list_applications()) == 1


def test_ac8_7_demo_data_has_the_required_spread(repo: SqlRepository) -> None:
    seed_if_empty(repo, TODAY)
    applications = repo.list_applications()
    assert len({a.status for a in applications}) >= 5
    assert {a.source for a in applications} == set(Source)
    assert len({a.company for a in applications}) == len(applications)
    assert list_followups(repo, TODAY), "at least one follow-up is due"
    for link in (a.link for a in applications if a.link):
        assert link.startswith("https://example.com/")


def test_ac8_7_histories_follow_the_status_rules(repo: SqlRepository) -> None:
    seed_if_empty(repo, TODAY)
    for application in repo.list_applications():
        events = repo.list_events(application.id)
        assert events[0].from_status is None and events[0].to_status == Status.SAVED
        for previous, event in zip(events, events[1:], strict=False):
            assert event.from_status == previous.to_status
        assert events[-1].to_status == application.status
        if application.status != Status.SAVED:
            assert application.applied_date is not None  # set by the "applied" rule
        if application.status in (Status.OFFER, Status.REJECTED, Status.GHOSTED, Status.SAVED):
            assert application.follow_up_date is None


def test_ac8_7_app_seeds_on_start_only_when_asked(engine: Engine) -> None:
    with TestClient(create_app(engine, migrate=False)) as client:
        assert client.get(f"{API}/applications").json() == []

    with TestClient(create_app(engine, migrate=False, seed=True)) as client:
        count = len(client.get(f"{API}/applications").json())
        assert 8 <= count <= 12

    # A restart does not add more.
    with TestClient(create_app(engine, migrate=False, seed=True)) as client:
        assert len(client.get(f"{API}/applications").json()) == count
