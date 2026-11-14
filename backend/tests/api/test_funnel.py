"""Issue #5: GET /api/v1/stats/funnel (AC-5.3 to AC-5.6)."""

from typing import Any

from fastapi.testclient import TestClient
from helpers import API, change_status, create_application

FUNNEL = f"{API}/stats/funnel"
STATUSES = ["saved", "applied", "screen", "interview", "offer", "rejected", "ghosted"]


def with_path(client: TestClient, company: str, source: str, *path: str) -> str:
    """Create an application and walk it through `path` (after the initial `saved`)."""
    app_id: str = create_application(client, company=company, source=source)["id"]
    for status in path:
        change_status(client, app_id, status)
    return app_id


def get_funnel(client: TestClient) -> dict[str, Any]:
    res = client.get(FUNNEL)
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


# ---- AC-5.3 shape -----------------------------------------------------------------


def test_ac5_3_shape(client: TestClient) -> None:
    with_path(client, "Alpha Labs", "inbound", "applied")
    body = get_funnel(client)
    assert set(body) == {"total", "by_status", "by_source"}
    assert body["total"] == 1
    assert list(body["by_status"]) == STATUSES
    assert [row["source"] for row in body["by_source"]] == ["cold", "inbound", "referral"]
    assert all(
        set(row) == {"source", "applied", "reached_screen", "screen_rate"} for row in body["by_source"]
    )


# ---- AC-5.4 empty database ----------------------------------------------------------


def test_ac5_4_empty_database(client: TestClient) -> None:
    assert get_funnel(client) == {
        "total": 0,
        "by_status": dict.fromkeys(STATUSES, 0),
        "by_source": [
            {"source": "cold", "applied": 0, "reached_screen": 0, "screen_rate": None},
            {"source": "inbound", "applied": 0, "reached_screen": 0, "screen_rate": None},
            {"source": "referral", "applied": 0, "reached_screen": 0, "screen_rate": None},
        ],
    }


# ---- AC-5.5 a mixed set, worked out by hand -----------------------------------------


def test_ac5_5_mixed_set_matches_hand_counts(client: TestClient) -> None:
    # cold: applied 3 (C1, C2, C4), reached screen 2 (C1, C4) -> 2/3 = 0.667
    with_path(client, "C1 Analytics", "cold", "applied", "screen", "rejected")
    with_path(client, "C2 Freight", "cold", "applied", "ghosted")
    with_path(client, "C3 Retail", "cold")
    with_path(client, "C4 Health", "cold", "interview", "offer")
    # inbound: applied 2 (I1, I3), reached screen 0 -> 0.0
    with_path(client, "I1 Systems", "inbound", "applied", "saved")
    with_path(client, "I2 Labs", "inbound", "rejected")
    with_path(client, "I3 Works", "inbound", "applied")
    # referral: applied 2 (R1, R2), reached screen 2 -> 1.0; R3 is deleted and counts nowhere
    with_path(client, "R1 Robotics", "referral", "screen", "interview")
    with_path(client, "R2 Energy", "referral", "applied", "ghosted", "screen")
    deleted = with_path(client, "R3 Media", "referral", "applied", "screen")
    assert client.delete(f"{API}/applications/{deleted}").status_code == 204

    assert get_funnel(client) == {
        "total": 9,
        "by_status": {
            "saved": 2,  # C3, I1
            "applied": 1,  # I3
            "screen": 1,  # R2
            "interview": 1,  # R1
            "offer": 1,  # C4
            "rejected": 2,  # C1, I2
            "ghosted": 1,  # C2
        },
        "by_source": [
            {"source": "cold", "applied": 3, "reached_screen": 2, "screen_rate": 0.667},
            {"source": "inbound", "applied": 2, "reached_screen": 0, "screen_rate": 0.0},
            {"source": "referral", "applied": 2, "reached_screen": 2, "screen_rate": 1.0},
        ],
    }


def test_ac5_5_one_in_three_is_0_333(client: TestClient) -> None:
    with_path(client, "Alpha Labs", "cold", "applied", "screen")
    with_path(client, "Beta Works", "cold", "applied")
    with_path(client, "Gamma Systems", "cold", "applied", "rejected")
    assert get_funnel(client)["by_source"][0] == {
        "source": "cold",
        "applied": 3,
        "reached_screen": 1,
        "screen_rate": 0.333,
    }


# ---- AC-5.6 from the events, not the current status -----------------------------------


def test_ac5_6_rejected_after_screen_counts_in_reached_screen(client: TestClient) -> None:
    with_path(client, "Delta Freight", "referral", "applied", "screen", "rejected")
    body = get_funnel(client)
    assert body["by_status"]["rejected"] == 1
    assert body["by_status"]["screen"] == 0
    assert body["by_source"][2] == {
        "source": "referral",
        "applied": 1,
        "reached_screen": 1,
        "screen_rate": 1.0,
    }


def test_ac5_6_moving_back_keeps_the_stage_reached(client: TestClient) -> None:
    with_path(client, "Epsilon Health", "inbound", "applied", "screen", "saved")
    body = get_funnel(client)
    assert body["by_status"]["saved"] == 1
    assert body["by_source"][1] == {
        "source": "inbound",
        "applied": 1,
        "reached_screen": 1,
        "screen_rate": 1.0,
    }


def test_ac5_6_patch_does_not_count(client: TestClient) -> None:
    app_id = create_application(client, company="Zeta Retail", source="cold")["id"]
    client.patch(f"{API}/applications/{app_id}", json={"applied_date": "2026-01-05"})
    assert get_funnel(client)["by_source"][0]["applied"] == 0


def test_ac5_6_deleted_application_counts_nowhere(client: TestClient) -> None:
    app_id = with_path(client, "Eta Logistics", "cold", "applied", "screen")
    assert get_funnel(client)["by_source"][0]["reached_screen"] == 1
    assert client.delete(f"{API}/applications/{app_id}").status_code == 204
    body = get_funnel(client)
    assert body["total"] == 0
    assert body["by_status"] == dict.fromkeys(STATUSES, 0)
    assert body["by_source"][0] == {"source": "cold", "applied": 0, "reached_screen": 0, "screen_rate": None}
