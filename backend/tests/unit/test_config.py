"""Config comes only from environment variables (AC-1.3 version rules, DATABASE_URL default)."""

import pytest

from app.config import DEFAULT_DATABASE_URL, app_version, database_url


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "APP_VERSION", "RENDER_GIT_COMMIT"):
        monkeypatch.delenv(name, raising=False)


def test_database_url_defaults_to_tracker_db() -> None:
    assert database_url() == DEFAULT_DATABASE_URL == "sqlite:///./tracker.db"


def test_database_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://tracker@localhost/tracker")
    assert database_url() == "postgresql+psycopg://tracker@localhost/tracker"


def test_ac1_3_version_prefers_app_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert app_version() == "1.2.3"


def test_ac1_3_version_falls_back_to_render_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert app_version() == "abc123"


def test_ac1_3_version_defaults_to_dev() -> None:
    assert app_version() == "dev"


def test_ac1_3_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert app_version() == "abc123"
