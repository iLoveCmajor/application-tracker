"""Small helpers shared by the API and integration tests."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

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
