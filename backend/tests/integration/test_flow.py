"""AC-9.3, AC-9.4: the whole flow through the HTTP app on PostgreSQL."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from helpers import API, MISSING_ID, assert_error, change_status, create_application, set_today
from sqlalchemy import Engine, func, select

from app.db.tables import status_events

DAY_1 = date(2026, 4, 1)


def test_ac9_3_full_flow(client: TestClient) -> None:
    set_today(client, DAY_1)
    app_id = create_application(client, company="Fernhill Data", role="MLOps Engineer", source="referral")[
        "id"
    ]
    other_id = create_application(client, company="Gullwing Labs", source="cold")["id"]
    create_application(client, company="Kestrel Works", source="inbound")  # stays saved

    applied = change_status(client, app_id, "applied", "Sent the form")
    assert applied["applied_date"] == "2026-04-01"
    assert applied["follow_up_date"] == "2026-04-08"
    change_status(client, other_id, "applied")

    set_today(client, date(2026, 4, 5))
    screen = change_status(client, app_id, "screen", "Recruiter call booked")
    assert screen["follow_up_date"] == "2026-04-08"  # kept

    events = client.get(f"{API}/applications/{app_id}/events").json()
    assert [(e["from_status"], e["to_status"], e["note"]) for e in events] == [
        (None, "saved", None),
        ("saved", "applied", "Sent the form"),
        ("applied", "screen", "Recruiter call booked"),
    ]

    set_today(client, date(2026, 4, 7))
    assert client.get(f"{API}/followups").json() == []
    set_today(client, date(2026, 4, 8))
    assert [a["company"] for a in client.get(f"{API}/followups").json()] == ["Fernhill Data", "Gullwing Labs"]

    rejected = change_status(client, app_id, "rejected", "Went with another candidate")
    assert rejected["follow_up_date"] is None
    assert [a["id"] for a in client.get(f"{API}/followups").json()] == [other_id]

    events = client.get(f"{API}/applications/{app_id}/events").json()
    assert [e["to_status"] for e in events] == ["saved", "applied", "screen", "rejected"]
    assert events[-1]["note"] == "Went with another candidate"
    stamps = [datetime.fromisoformat(e["created_at"]) for e in events]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)

    funnel = client.get(f"{API}/stats/funnel").json()
    assert funnel["total"] == 3
    assert funnel["by_status"] == {
        "saved": 1,
        "applied": 1,
        "screen": 0,
        "interview": 0,
        "offer": 0,
        "rejected": 1,
        "ghosted": 0,
    }
    by_source = {row["source"]: row for row in funnel["by_source"]}
    assert by_source["referral"] == {
        "source": "referral",
        "applied": 1,
        "reached_screen": 1,
        "screen_rate": 1.0,
    }
    assert by_source["cold"] == {"source": "cold", "applied": 1, "reached_screen": 0, "screen_rate": 0.0}
    assert by_source["inbound"] == {
        "source": "inbound",
        "applied": 0,
        "reached_screen": 0,
        "screen_rate": None,
    }


def test_ac9_4_delete_removes_the_events(client: TestClient, engine: Engine) -> None:
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    keep_id = create_application(client, company="Gullwing Labs")["id"]

    assert client.delete(f"{API}/applications/{app_id}").status_code == 204
    assert_error(client.get(f"{API}/applications/{app_id}"), 404, "not_found")
    with engine.connect() as connection:
        count = select(func.count()).select_from(status_events)
        assert connection.execute(count.where(status_events.c.application_id == app_id)).scalar() == 0
        assert connection.execute(count.where(status_events.c.application_id == keep_id)).scalar() == 1


def test_ac9_4_database_cascade_on_delete(client: TestClient, engine: Engine) -> None:
    """The foreign key itself removes events, not only the repository's explicit delete."""
    app_id = create_application(client)["id"]
    change_status(client, app_id, "applied")
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM applications WHERE id = %s", (app_id,))
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(status_events)).scalar() == 0


def test_ac9_4_timestamps_are_iso_8601_utc(client: TestClient) -> None:
    created = create_application(client)
    app_id = created["id"]
    updated = change_status(client, app_id, "applied")
    events = client.get(f"{API}/applications/{app_id}/events").json()
    stamps = [created["created_at"], created["updated_at"], updated["updated_at"]]
    stamps += [e["created_at"] for e in events]
    stamps += [a["updated_at"] for a in client.get(f"{API}/applications").json()]
    for stamp in stamps:
        assert stamp.endswith(("Z", "+00:00")), stamp
        parsed = datetime.fromisoformat(stamp)
        assert parsed.utcoffset() == UTC.utcoffset(None)
    assert client.get(f"{API}/applications/{MISSING_ID}").status_code == 404
