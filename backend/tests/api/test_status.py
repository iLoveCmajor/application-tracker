"""Issue #3: status change with history and the date rules (AC-3.2 to AC-3.9)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from helpers import (
    API,
    MISSING_ID,
    RepoFactory,
    assert_error,
    change_status,
    create_application,
    is_later,
    set_today,
)
from sqlalchemy import Engine, func, select

from app.db.tables import status_events
from app.main import create_app
from app.repositories.sql import SqlRepository

APPS = f"{API}/applications"
EVENT_FIELDS = {"id", "application_id", "from_status", "to_status", "note", "created_at"}


def status_url(application_id: str) -> str:
    return f"{APPS}/{application_id}/status"


def events_url(application_id: str) -> str:
    return f"{APPS}/{application_id}/events"


def event_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(select(func.count()).select_from(status_events)).scalar_one())


# ---- AC-3.2 move to applied -----------------------------------------------------


def test_ac3_2_applied_sets_dates_and_bumps_updated_at(client: TestClient, today: date) -> None:
    created = create_application(client)
    res = client.post(status_url(created["id"]), json={"status": "applied"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == created["id"]
    assert body["status"] == "applied"
    assert body["applied_date"] == today.isoformat()
    assert body["follow_up_date"] == (today + timedelta(days=7)).isoformat()
    assert is_later(body["updated_at"], created["updated_at"])
    assert body["created_at"] == created["created_at"]
    assert {k: body[k] for k in ("company", "role", "source", "link", "notes")} == {
        k: created[k] for k in ("company", "role", "source", "link", "notes")
    }
    assert client.get(f"{APPS}/{created['id']}").json() == body


def test_ac3_2_without_override_today_is_the_utc_date(client: TestClient) -> None:
    before = datetime.now(UTC).date()
    body = change_status(client, create_application(client)["id"], "applied")
    after = datetime.now(UTC).date()
    assert body["applied_date"] in {before.isoformat(), after.isoformat()}


# ---- AC-3.3 any status to any other ---------------------------------------------


def test_ac3_3_ghosted_to_screen(client: TestClient, today: date) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    change_status(client, app_id, "ghosted")
    body = change_status(client, app_id, "screen")
    assert body["status"] == "screen"
    assert body["applied_date"] == today.isoformat()
    assert body["follow_up_date"] is None


def test_ac3_3_rejected_to_applied_keeps_applied_date(client: TestClient, today: date) -> None:
    app_id = create_application(client)["id"]
    first_day = today - timedelta(days=30)
    set_today(client, first_day)
    change_status(client, app_id, "applied")
    change_status(client, app_id, "rejected")

    set_today(client, today)
    body = change_status(client, app_id, "applied")
    assert body["applied_date"] == first_day.isoformat()
    assert body["follow_up_date"] == (today + timedelta(days=7)).isoformat()


@pytest.mark.parametrize("closing", ["offer", "rejected", "ghosted"])
def test_ac3_3_closing_statuses_clear_follow_up(client: TestClient, today: date, closing: str) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    body = change_status(client, app_id, closing)
    assert body["applied_date"] == today.isoformat()
    assert body["follow_up_date"] is None


@pytest.mark.parametrize("keeping", ["saved", "screen", "interview"])
def test_ac3_3_other_statuses_keep_dates(client: TestClient, today: date, keeping: str) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    if keeping == "saved":
        change_status(client, app_id, "screen")
    set_today(client, today + timedelta(days=3))
    body = change_status(client, app_id, keeping)
    assert body["applied_date"] == today.isoformat()
    assert body["follow_up_date"] == (today + timedelta(days=7)).isoformat()


def test_ac3_3_dates_set_by_patch_follow_the_rules(client: TestClient, today: date) -> None:
    app_id = create_application(client)["id"]
    client.patch(f"{APPS}/{app_id}", json={"applied_date": "2026-01-05", "follow_up_date": "2026-01-12"})
    body = change_status(client, app_id, "interview")
    assert (body["applied_date"], body["follow_up_date"]) == ("2026-01-05", "2026-01-12")
    body = change_status(client, app_id, "applied")
    assert (body["applied_date"], body["follow_up_date"]) == ("2026-01-05", "2026-03-17")


# ---- AC-3.4 same status ---------------------------------------------------------


def test_ac3_4_same_status_is_invalid_transition(client: TestClient, engine: Engine, today: date) -> None:
    app_id = create_application(client)["id"]
    applied = change_status(client, app_id, "applied")
    count = event_count(engine)

    set_today(client, today + timedelta(days=2))
    error = assert_error(
        client.post(status_url(app_id), json={"status": "applied"}), 409, "invalid_transition"
    )
    assert error["details"] == {"status": "applied"}
    assert client.get(f"{APPS}/{app_id}").json() == applied
    assert event_count(engine) == count


def test_ac3_4_saved_to_saved_is_invalid_transition(client: TestClient, engine: Engine) -> None:
    created = create_application(client)
    assert_error(client.post(status_url(created["id"]), json={"status": "saved"}), 409, "invalid_transition")
    assert client.get(f"{APPS}/{created['id']}").json() == created
    assert event_count(engine) == 1


# ---- AC-3.5 validation and not found --------------------------------------------


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({}, "status"),
        ({"note": "no status"}, "status"),
        ({"status": "bogus"}, "status"),
        ({"status": "Applied"}, "status"),
        ({"status": None}, "status"),
        ({"status": 3}, "status"),
        ({"status": ["applied"]}, "status"),
        ({"status": "applied", "note": "x" * 501}, "note"),
        ({"status": "applied", "note": 42}, "note"),
        ({"status": "applied", "note": ["a"]}, "note"),
        ({"status": "applied", "applied_date": "2026-01-01"}, "applied_date"),
        ({"status": "applied", "from_status": "saved"}, "from_status"),
    ],
)
def test_ac3_5_bad_body_is_a_validation_error(
    client: TestClient, engine: Engine, body: dict[str, Any], field: str
) -> None:
    created = create_application(client)
    error = assert_error(client.post(status_url(created["id"]), json=body), 422, "validation_error")
    assert error["details"]["field"] == field
    assert client.get(f"{APPS}/{created['id']}").json() == created
    assert event_count(engine) == 1


def test_ac3_5_non_object_body_is_a_validation_error(client: TestClient) -> None:
    created = create_application(client)
    assert_error(client.post(status_url(created["id"]), json="applied"), 422, "validation_error")
    assert_error(
        client.post(status_url(created["id"]), content=b"{", headers={"content-type": "application/json"}),
        422,
        "validation_error",
    )


def test_ac3_5_note_of_500_chars_is_accepted(client: TestClient, repo_factory: RepoFactory) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied", note="x" * 500)
    with repo_factory() as repo:
        assert repo.list_events(UUID(app_id))[-1].note == "x" * 500


@pytest.mark.parametrize("bad_id", [MISSING_ID, "abc", "123"])
def test_ac3_5_unknown_or_malformed_id_is_not_found(client: TestClient, bad_id: str) -> None:
    assert_error(client.post(status_url(bad_id), json={"status": "applied"}), 404, "not_found")


# ---- AC-3.6 one event per change -------------------------------------------------


def test_ac3_6_each_change_writes_one_event(client: TestClient, engine: Engine) -> None:
    app_id = create_application(client)["id"]
    applied = change_status(client, app_id, "applied", note="Sent through the careers page.")
    assert event_count(engine) == 2
    screen = change_status(client, app_id, "screen")
    assert event_count(engine) == 3

    events = client.get(events_url(app_id)).json()
    assert [(e["from_status"], e["to_status"], e["note"]) for e in events] == [
        (None, "saved", None),
        ("saved", "applied", "Sent through the careers page."),
        ("applied", "screen", None),
    ]
    assert events[1]["created_at"] == applied["updated_at"]
    assert events[2]["created_at"] == screen["updated_at"]


def test_ac3_6_explicit_null_note_is_stored_as_null(client: TestClient) -> None:
    app_id = create_application(client)["id"]
    res = client.post(status_url(app_id), json={"status": "applied", "note": None})
    assert res.status_code == 200
    assert client.get(events_url(app_id)).json()[-1]["note"] is None


# ---- AC-3.7 one transaction -----------------------------------------------------


def test_ac3_7_failed_event_write_rolls_back_the_change(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(engine, migrate=False), raise_server_exceptions=False)
    set_today(client, date(2026, 3, 10))
    created = create_application(client)

    def broken_add_event(self: SqlRepository, record: Any) -> None:
        raise RuntimeError("event write failed")

    monkeypatch.setattr(SqlRepository, "add_event", broken_add_event)
    error = assert_error(
        client.post(status_url(created["id"]), json={"status": "applied"}), 500, "internal_error"
    )
    assert "event write failed" not in str(error)

    after = client.get(f"{APPS}/{created['id']}").json()
    assert after == created
    assert (after["status"], after["applied_date"], after["follow_up_date"]) == ("saved", None, None)
    assert event_count(engine) == 1


# ---- AC-3.8 history --------------------------------------------------------------


def test_ac3_8_events_oldest_first_starting_with_creation(client: TestClient) -> None:
    created = create_application(client)
    app_id = created["id"]
    for status in ["applied", "screen", "interview", "rejected", "applied"]:
        change_status(client, app_id, status)

    res = client.get(events_url(app_id))
    assert res.status_code == 200
    events = res.json()
    assert all(set(e) == EVENT_FIELDS for e in events)
    assert all(e["application_id"] == app_id for e in events)
    assert events[0]["from_status"] is None and events[0]["to_status"] == "saved"
    assert events[0]["created_at"] == created["created_at"]
    assert [e["to_status"] for e in events] == [
        "saved",
        "applied",
        "screen",
        "interview",
        "rejected",
        "applied",
    ]
    assert [e["from_status"] for e in events[1:]] == [e["to_status"] for e in events[:-1]]
    stamps = [e["created_at"] for e in events]
    assert all(is_later(b, a) for a, b in zip(stamps, stamps[1:], strict=False))
    assert len({e["id"] for e in events}) == len(events)


def test_ac3_8_events_belong_to_one_application(client: TestClient) -> None:
    a = create_application(client, company="Alpha Labs")["id"]
    b = create_application(client, company="Beta Works")["id"]
    change_status(client, a, "applied")
    assert [e["to_status"] for e in client.get(events_url(b)).json()] == ["saved"]


@pytest.mark.parametrize("bad_id", [MISSING_ID, "abc"])
def test_ac3_8_unknown_or_malformed_id_is_not_found(client: TestClient, bad_id: str) -> None:
    assert_error(client.get(events_url(bad_id)), 404, "not_found")


def test_ac3_8_deleted_application_has_no_history(client: TestClient) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    assert client.delete(f"{APPS}/{app_id}").status_code == 204
    assert_error(client.get(events_url(app_id)), 404, "not_found")
    assert_error(client.post(status_url(app_id), json={"status": "screen"}), 404, "not_found")


# ---- AC-3.9 today comes from the clock dependency --------------------------------


def test_ac3_9_today_follows_the_overridden_clock(client: TestClient) -> None:
    app_id = create_application(client)["id"]
    set_today(client, date(2030, 12, 30))
    body = change_status(client, app_id, "applied")
    assert (body["applied_date"], body["follow_up_date"]) == ("2030-12-30", "2031-01-06")
