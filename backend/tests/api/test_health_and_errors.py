"""AC-1.3 to AC-1.6: /health, /ready and the error format."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import API, assert_error

from app.db.engine import create_db_engine
from app.main import create_app


@pytest.fixture
def no_version_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)


# ---- AC-1.3 ---------------------------------------------------------------------


def test_ac1_3_health_uses_app_version(
    client: TestClient, no_version_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_VERSION", "1.4.0")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0123abc")
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "1.4.0"}


def test_ac1_3_health_falls_back_to_render_git_commit(
    client: TestClient, no_version_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0123abc")
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0123abc"}


def test_ac1_3_health_defaults_to_dev(client: TestClient, no_version_env: None) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "dev"}


# ---- AC-1.4 ---------------------------------------------------------------------


def test_ac1_4_ready_when_the_database_answers(client: TestClient) -> None:
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ac1_4_not_ready_when_the_database_is_unreachable() -> None:
    broken = create_db_engine("sqlite:////nonexistent-dir/for-this-test/tracker.db")
    client = TestClient(create_app(broken, migrate=False))
    assert_error(client.get("/ready"), 503, "service_unavailable")
    # The process itself is still up.
    assert client.get("/health").status_code == 200


# ---- AC-1.5 ---------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_ac1_5_health_and_ready_are_outside_the_api_prefix(client: TestClient, path: str) -> None:
    assert_error(client.get(f"{API}{path}"), 404, "not_found")


# ---- AC-1.6 ---------------------------------------------------------------------


def test_ac1_6_unknown_route_uses_the_error_format(client: TestClient) -> None:
    assert_error(client.get(f"{API}/nope"), 404, "not_found")
    assert_error(client.get("/nope"), 404, "not_found")


def test_ac1_6_unhandled_exception_is_internal_error_without_traceback(client: TestClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)

    def boom() -> None:
        raise RuntimeError("boom: secret detail")

    app.add_api_route("/test-only/boom", boom)
    failing = TestClient(app, raise_server_exceptions=False)
    res = failing.get("/test-only/boom")
    error = assert_error(res, 500, "internal_error")
    assert error["details"] == {}
    assert "Traceback" not in res.text
    assert "boom" not in res.text
    assert "RuntimeError" not in res.text
