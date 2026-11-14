"""Issue #2: applications CRUD (AC-2.1 to AC-2.8)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from helpers import API, MISSING_ID, RepoFactory, assert_error, create_application, is_later
from sqlalchemy import Engine, func, select

from app.db.tables import status_events
from app.domain import Status

APPS = f"{API}/applications"
ALL_FIELDS = {
    "id",
    "company",
    "role",
    "link",
    "source",
    "status",
    "applied_date",
    "follow_up_date",
    "notes",
    "created_at",
    "updated_at",
}
VALID = {"company": "Northwind Analytics", "role": "ML Engineer", "source": "cold"}


def event_count(engine: Engine, application_id: str) -> int:
    with engine.connect() as connection:
        stmt = select(func.count()).where(status_events.c.application_id == UUID(application_id))
        return int(connection.execute(stmt).scalar_one())


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() is not None and parsed.utcoffset() == UTC.utcoffset(None), value
    return parsed


# ---- AC-2.1 create --------------------------------------------------------------


def test_ac2_1_create_returns_the_new_application(client: TestClient) -> None:
    res = client.post(
        APPS,
        json={
            "company": "  Northwind Analytics  ",
            "role": "\tML Engineer ",
            "source": "referral",
            "link": "https://jobs.example.com/northwind/42",
            "notes": "Met their lead at a meetup.",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == ALL_FIELDS
    assert UUID(body["id"])
    assert body["company"] == "Northwind Analytics"
    assert body["role"] == "ML Engineer"
    assert body["source"] == "referral"
    assert body["link"] == "https://jobs.example.com/northwind/42"
    assert body["notes"] == "Met their lead at a meetup."
    assert body["status"] == "saved"
    assert body["applied_date"] is None
    assert body["follow_up_date"] is None
    assert parse_utc(body["created_at"]) == parse_utc(body["updated_at"])


def test_ac2_1_link_and_notes_are_optional(client: TestClient) -> None:
    body = create_application(client)
    assert body["link"] is None
    assert body["notes"] is None


def test_ac2_1_ids_are_generated_by_the_server(client: TestClient) -> None:
    assert create_application(client)["id"] != create_application(client)["id"]


# ---- AC-2.2 event on create -----------------------------------------------------


def test_ac2_2_create_writes_one_saved_event(client: TestClient, repo_factory: RepoFactory) -> None:
    created = create_application(client)
    with repo_factory() as repo:
        events = repo.list_events(UUID(created["id"]))
    assert len(events) == 1
    [event] = events
    assert event.from_status is None
    assert event.to_status == Status.SAVED
    assert event.note is None


def test_ac2_2_failed_create_writes_no_event(client: TestClient, engine: Engine) -> None:
    assert_error(client.post(APPS, json={**VALID, "company": ""}), 422, "validation_error")
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(status_events)).scalar_one() == 0


# ---- AC-2.3 validation on create ------------------------------------------------


@pytest.mark.parametrize("missing", ["company", "role", "source"])
def test_ac2_3_required_fields(client: TestClient, missing: str) -> None:
    body = {k: v for k, v in VALID.items() if k != missing}
    error = assert_error(client.post(APPS, json=body), 422, "validation_error")
    assert error["details"]["field"] == missing


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("company", ""),
        ("company", "   "),
        ("role", ""),
        ("role", " \t "),
        ("company", "x" * 101),
        ("role", "x" * 101),
        ("company", "  " + "x" * 101 + "  "),
        ("link", "https://example.com/" + "x" * 481),  # 501 chars
        ("link", "ftp://example.com/job"),
        ("link", "example.com/job"),
        ("link", " https://example.com/job"),
        ("notes", "x" * 5001),
        ("source", "agency"),
        ("source", "Cold"),
        ("company", 123),
        ("role", ["ML Engineer"]),
        ("source", 1),
        ("notes", True),
        ("link", 42),
        ("status", "applied"),
        ("status", "saved"),
        ("priority", "high"),
    ],
)
def test_ac2_3_create_rejects_invalid_values(client: TestClient, field: str, value: Any) -> None:
    error = assert_error(client.post(APPS, json={**VALID, field: value}), 422, "validation_error")
    assert error["details"]["field"] == field


@pytest.mark.parametrize(
    ("field", "value", "stored"),
    [
        ("company", "x" * 100, "x" * 100),
        ("company", "  " + "x" * 100 + "  ", "x" * 100),
        ("role", "y" * 100, "y" * 100),
        ("link", "https://example.com/" + "x" * 480, "https://example.com/" + "x" * 480),
        ("link", "http://example.com/job", "http://example.com/job"),
        ("notes", "n" * 5000, "n" * 5000),
        ("source", "inbound", "inbound"),
    ],
)
def test_ac2_3_create_accepts_boundary_values(
    client: TestClient, field: str, value: str, stored: str
) -> None:
    assert create_application(client, **{field: value})[field] == stored


def test_ac2_3_invalid_json_is_a_validation_error(client: TestClient) -> None:
    res = client.post(APPS, content=b"{not json", headers={"Content-Type": "application/json"})
    assert_error(res, 422, "validation_error")


def test_ac2_3_rejected_create_stores_nothing(client: TestClient) -> None:
    client.post(APPS, json={**VALID, "status": "offer"})
    assert client.get(APPS).json() == []


# ---- AC-2.4 get -----------------------------------------------------------------


def test_ac2_4_get_returns_the_application(client: TestClient) -> None:
    created = create_application(client, link="https://jobs.example.com/1")
    res = client.get(f"{APPS}/{created['id']}")
    assert res.status_code == 200
    assert res.json() == created


@pytest.mark.parametrize("bad_id", [MISSING_ID, "abc", "123"])
def test_ac2_4_unknown_or_malformed_id_is_not_found(client: TestClient, bad_id: str) -> None:
    create_application(client)
    assert_error(client.get(f"{APPS}/{bad_id}"), 404, "not_found")


# ---- AC-2.5 list ----------------------------------------------------------------


def test_ac2_5_empty_list(client: TestClient) -> None:
    res = client.get(APPS)
    assert res.status_code == 200
    assert res.json() == []


def test_ac2_5_list_is_newest_updated_first(client: TestClient) -> None:
    a = create_application(client, company="Alpha Labs")
    b = create_application(client, company="Beta Works")
    c = create_application(client, company="Gamma Systems")
    assert [x["company"] for x in client.get(APPS).json()] == ["Gamma Systems", "Beta Works", "Alpha Labs"]

    client.patch(f"{APPS}/{a['id']}", json={"notes": "edited"})
    assert [x["id"] for x in client.get(APPS).json()] == [a["id"], c["id"], b["id"]]


def test_ac2_5_filter_by_status(client: TestClient, repo_factory: RepoFactory) -> None:
    saved = create_application(client, company="Saved Co")
    applied = create_application(client, company="Applied Co")
    # The status endpoint comes in #3; set the status through the repository for now.
    with repo_factory() as repo, repo.transaction():
        record = repo.get_application(UUID(applied["id"]))
        assert record is not None
        record.status = Status.APPLIED
        repo.save_application(record)

    res = client.get(APPS, params={"status": "applied"})
    assert res.status_code == 200
    assert [x["id"] for x in res.json()] == [applied["id"]]
    assert [x["id"] for x in client.get(APPS, params={"status": "saved"}).json()] == [saved["id"]]
    assert client.get(APPS, params={"status": "offer"}).json() == []
    assert len(client.get(APPS).json()) == 2


@pytest.mark.parametrize("bad", ["bogus", "Applied", ""])
def test_ac2_5_unknown_status_filter_is_a_validation_error(client: TestClient, bad: str) -> None:
    error = assert_error(client.get(APPS, params={"status": bad}), 422, "validation_error")
    assert error["details"]["field"] == "status"


# ---- AC-2.6 patch ---------------------------------------------------------------


def test_ac2_6_patch_changes_only_the_fields_sent(client: TestClient) -> None:
    created = create_application(client, link="https://jobs.example.com/1", notes="first")
    res = client.patch(f"{APPS}/{created['id']}", json={"role": "  Senior ML Engineer  "})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == "Senior ML Engineer"
    unchanged = {k: v for k, v in created.items() if k not in ("role", "updated_at")}
    assert {k: v for k, v in body.items() if k not in ("role", "updated_at")} == unchanged
    assert is_later(body["updated_at"], created["updated_at"])
    assert client.get(f"{APPS}/{created['id']}").json() == body


def test_ac2_6_patch_every_editable_field(client: TestClient) -> None:
    created = create_application(client)
    changes = {
        "company": "Contoso Robotics",
        "role": "MLOps Engineer",
        "link": "http://careers.example.org/7",
        "source": "inbound",
        "applied_date": "2026-11-02",
        "follow_up_date": "2026-11-09",
        "notes": "Recruiter reached out.",
    }
    body = client.patch(f"{APPS}/{created['id']}", json=changes).json()
    assert {k: body[k] for k in changes} == changes
    assert body["status"] == "saved"


def test_ac2_6_null_clears_optional_fields(client: TestClient) -> None:
    created = create_application(client, link="https://jobs.example.com/1", notes="n")
    client.patch(
        f"{APPS}/{created['id']}", json={"applied_date": "2026-11-02", "follow_up_date": "2026-11-09"}
    )
    res = client.patch(
        f"{APPS}/{created['id']}",
        json={"link": None, "notes": None, "applied_date": None, "follow_up_date": None},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["link"], body["notes"], body["applied_date"], body["follow_up_date"]) == (None,) * 4


def test_ac2_6_empty_patch_changes_nothing_but_updated_at(client: TestClient) -> None:
    created = create_application(client)
    body = client.patch(f"{APPS}/{created['id']}", json={}).json()
    assert {k: v for k, v in body.items() if k != "updated_at"} == {
        k: v for k, v in created.items() if k != "updated_at"
    }
    assert is_later(body["updated_at"], created["updated_at"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("company", None),
        ("role", None),
        ("source", None),
        ("company", ""),
        ("role", "   "),
        ("company", "x" * 101),
        ("link", "https://example.com/" + "x" * 481),
        ("link", "mailto:jobs@example.com"),
        ("notes", "x" * 5001),
        ("source", "agency"),
        ("applied_date", "2026-13-01"),
        ("follow_up_date", "2026-02-30"),
        ("applied_date", "next week"),
        ("company", 5),
        ("priority", "high"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("id", MISSING_ID),
    ],
)
def test_ac2_6_patch_rejects_invalid_values(client: TestClient, field: str, value: Any) -> None:
    created = create_application(client)
    error = assert_error(
        client.patch(f"{APPS}/{created['id']}", json={field: value}), 422, "validation_error"
    )
    assert error["details"]["field"] == field
    assert client.get(f"{APPS}/{created['id']}").json() == created


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("company", "x" * 100),
        ("link", "https://example.com/" + "x" * 480),
        ("notes", "x" * 5000),
    ],
)
def test_ac2_6_patch_accepts_boundary_values(client: TestClient, field: str, value: str) -> None:
    created = create_application(client)
    res = client.patch(f"{APPS}/{created['id']}", json={field: value})
    assert res.status_code == 200, res.text
    assert res.json()[field] == value


@pytest.mark.parametrize("bad_id", [MISSING_ID, "abc"])
def test_ac2_6_patch_unknown_id_is_not_found(client: TestClient, bad_id: str) -> None:
    assert_error(client.patch(f"{APPS}/{bad_id}", json={"notes": "x"}), 404, "not_found")


# ---- AC-2.7 patch cannot change status ------------------------------------------


@pytest.mark.parametrize(
    "body", [{"status": "applied"}, {"status": "applied", "notes": "x"}, {"status": None}]
)
def test_ac2_7_patch_with_status_is_rejected(client: TestClient, body: dict[str, Any]) -> None:
    created = create_application(client)
    error = assert_error(client.patch(f"{APPS}/{created['id']}", json=body), 422, "validation_error")
    assert error["details"]["field"] == "status"
    after = client.get(f"{APPS}/{created['id']}").json()
    assert after["status"] == "saved"
    assert after == created


# ---- AC-2.8 delete --------------------------------------------------------------


def test_ac2_8_delete_removes_the_application_and_its_events(client: TestClient, engine: Engine) -> None:
    kept = create_application(client, company="Kept Co")
    created = create_application(client)
    assert event_count(engine, created["id"]) == 1

    res = client.delete(f"{APPS}/{created['id']}")
    assert res.status_code == 204
    assert res.content == b""

    assert_error(client.get(f"{APPS}/{created['id']}"), 404, "not_found")
    assert event_count(engine, created["id"]) == 0
    assert_error(client.delete(f"{APPS}/{created['id']}"), 404, "not_found")

    assert [x["id"] for x in client.get(APPS).json()] == [kept["id"]]
    assert event_count(engine, kept["id"]) == 1


def test_ac2_8_delete_malformed_id_is_not_found(client: TestClient) -> None:
    assert_error(client.delete(f"{APPS}/abc"), 404, "not_found")
