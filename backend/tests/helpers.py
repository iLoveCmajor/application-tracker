"""Small helpers shared by the API and integration tests."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any

from app.api.deps import get_today
from app.repositories.sql import SqlRepository

API = "/api/v1"
MISSING_ID = "00000000-0000-4000-8000-000000000000"

RepoFactory = Callable[[], AbstractContextManager[SqlRepository]]


def assert_error(res: Any, status: int, code: str) -> dict[str, Any]:
    """The response is `status` with the spec's error body, and returns that body's `error`."""
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert isinstance(body["error"]["details"], dict)
    return body["error"]


def is_later(a: str, b: str) -> bool:
    """True if timestamp `a` is after `b`."""
    return datetime.fromisoformat(a) > datetime.fromisoformat(b)


def create_application(client: Any, **fields: Any) -> dict[str, Any]:
    """POST a valid invented application, with `fields` overriding the defaults."""
    body = {"company": "Northwind Analytics", "role": "ML Engineer", "source": "cold"} | fields
    res = client.post(f"{API}/applications", json=body)
    assert res.status_code == 201, res.text
    result: dict[str, Any] = res.json()
    return result


def set_today(client: Any, today: date) -> None:
    """Fix "today" for the app behind `client` by overriding the clock dependency."""
    client.app.dependency_overrides[get_today] = lambda: today


def change_status(client: Any, application_id: str, status: str, note: str | None = None) -> dict[str, Any]:
    """POST a status change that must succeed, and return the application."""
    body: dict[str, Any] = {"status": status} if note is None else {"status": status, "note": note}
    res = client.post(f"{API}/applications/{application_id}/status", json=body)
    assert res.status_code == 200, res.text
    result: dict[str, Any] = res.json()
    return result
