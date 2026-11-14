"""Config comes only from environment variables (AC-1.3 version rules, DATABASE_URL default)."""

from pathlib import Path

import pytest

from app.config import DEFAULT_DATABASE_URL, app_version, database_url, seed_demo_data, static_dir


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "APP_VERSION", "RENDER_GIT_COMMIT", "SEED_DEMO_DATA", "STATIC_DIR"):
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


def test_ac8_7_seed_is_off_when_unset() -> None:
    assert seed_demo_data() is False


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes"])
def test_ac8_7_seed_is_on_for_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SEED_DEMO_DATA", value)
    assert seed_demo_data() is True


@pytest.mark.parametrize("value", ["false", "0", "", "no"])
def test_ac8_7_seed_is_off_for_false_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SEED_DEMO_DATA", value)
    assert seed_demo_data() is False


def test_static_dir_is_unset_by_default() -> None:
    assert static_dir() is None


def test_static_dir_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STATIC_DIR", "/app/static")
    assert static_dir() == Path("/app/static")
