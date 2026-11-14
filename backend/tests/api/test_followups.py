"""Issue #4: GET /api/v1/followups (AC-4.2 to AC-4.6)."""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from helpers import API, change_status, create_application, set_today

FOLLOWUPS = f"{API}/followups"
APPS = f"{API}/applications"


def applied_on(client: TestClient, day: date, **fields: Any) -> dict[str, Any]:
    """An application moved to `applied` on `day`, so its follow-up is `day` + 7."""
    set_today(client, day)
    return change_status(client, create_application(client, **fields)["id"], "applied")


def companies(client: TestClient) -> list[str]:
    res = client.get(FOLLOWUPS)
    assert res.status_code == 200, res.text
    return [a["company"] for a in res.json()]


# ---- AC-4.2 the list ------------------------------------------------------------


def test_ac4_2_lists_due_applications_in_the_application_shape(client: TestClient, today: date) -> None:
    due = applied_on(client, today - timedelta(days=8), company="Overdue Co")
    applied_on(client, today, company="Fresh Co")
    set_today(client, today)

    res = client.get(FOLLOWUPS)
    assert res.status_code == 200
    body = res.json()
    assert body == [client.get(f"{APPS}/{due['id']}").json()]
    assert body[0]["follow_up_date"] == (today - timedelta(days=1)).isoformat()


def test_ac4_2_status_decides_after_status_changes(client: TestClient, today: date) -> None:
    week_ago = today - timedelta(days=7)
    screen = applied_on(client, week_ago, company="Screen Co")
    interview = applied_on(client, week_ago, company="Interview Co")
    ghosted = applied_on(client, week_ago, company="Ghosted Co")
    saved = applied_on(client, week_ago, company="Saved Again Co")
    change_status(client, screen["id"], "screen")
    change_status(client, interview["id"], "interview")
    change_status(client, ghosted["id"], "ghosted")
    change_status(client, saved["id"], "saved")  # keeps its follow_up_date, but saved is not due

    set_today(client, today)
    assert companies(client) == ["Interview Co", "Screen Co"]


def test_ac4_2_without_override_uses_the_real_date(client: TestClient) -> None:
    applied_on(client, date(2020, 1, 1), company="Long Ago Co")
    client.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    assert companies(client) == ["Long Ago Co"]


# ---- AC-4.3 dates set by PATCH --------------------------------------------------


def test_ac4_3_patched_dates_follow_the_same_rule(client: TestClient, today: date) -> None:
    past = (today - timedelta(days=3)).isoformat()

    rejected = applied_on(client, today, company="Rejected Co")
    change_status(client, rejected["id"], "rejected")
    client.patch(f"{APPS}/{rejected['id']}", json={"follow_up_date": past})

    saved = create_application(client, company="Saved Co")
    client.patch(f"{APPS}/{saved['id']}", json={"follow_up_date": past})

    pulled_in = applied_on(client, today, company="Pulled In Co")
    client.patch(f"{APPS}/{pulled_in['id']}", json={"follow_up_date": past})

    pushed_out = applied_on(client, today - timedelta(days=10), company="Pushed Out Co")
    client.patch(
        f"{APPS}/{pushed_out['id']}", json={"follow_up_date": (today + timedelta(days=5)).isoformat()}
    )

    cleared = applied_on(client, today - timedelta(days=10), company="Cleared Co")
    client.patch(f"{APPS}/{cleared['id']}", json={"follow_up_date": None})

    set_today(client, today)
    assert companies(client) == ["Pulled In Co"]


# ---- AC-4.4 ordering -------------------------------------------------------------


def test_ac4_4_ordered_by_follow_up_date_then_company(client: TestClient, today: date) -> None:
    applied_on(client, today - timedelta(days=7), company="Gamma Systems")
    applied_on(client, today - timedelta(days=9), company="Delta Freight")
    applied_on(client, today - timedelta(days=7), company="Alpha Labs")
    applied_on(client, today - timedelta(days=9), company="Beta Works")
    applied_on(client, today - timedelta(days=20), company="Zeta Retail")

    set_today(client, today)
    body = client.get(FOLLOWUPS).json()
    assert [(a["follow_up_date"], a["company"]) for a in body] == [
        ((today - timedelta(days=13)).isoformat(), "Zeta Retail"),
        ((today - timedelta(days=2)).isoformat(), "Beta Works"),
        ((today - timedelta(days=2)).isoformat(), "Delta Freight"),
        (today.isoformat(), "Alpha Labs"),
        (today.isoformat(), "Gamma Systems"),
    ]


# ---- AC-4.5 nothing due ----------------------------------------------------------


def test_ac4_5_empty_database_is_an_empty_list(client: TestClient, today: date) -> None:
    res = client.get(FOLLOWUPS)
    assert res.status_code == 200
    assert res.json() == []


def test_ac4_5_nothing_due_is_an_empty_list(client: TestClient, today: date) -> None:
    create_application(client, company="Saved Co")
    applied_on(client, today, company="Fresh Co")
    set_today(client, today)
    assert client.get(FOLLOWUPS).json() == []


# ---- AC-4.6 boundary through the clock dependency --------------------------------


def test_ac4_6_today_included_tomorrow_excluded(client: TestClient, today: date) -> None:
    applied_on(client, today - timedelta(days=7), company="Due Today Co")
    applied_on(client, today - timedelta(days=6), company="Due Tomorrow Co")

    set_today(client, today)
    assert companies(client) == ["Due Today Co"]

    set_today(client, today - timedelta(days=1))
    assert companies(client) == []

    set_today(client, today + timedelta(days=1))
    assert companies(client) == ["Due Today Co", "Due Tomorrow Co"]
