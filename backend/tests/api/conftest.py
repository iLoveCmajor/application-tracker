from datetime import date

import pytest
from fastapi.testclient import TestClient
from helpers import set_today


@pytest.fixture(autouse=True)
def _clean_database(empty_tables: None) -> None:
    """Every API test starts with empty tables."""


@pytest.fixture
def today(client: TestClient) -> date:
    """A fixed "today" for the app, set through the clock dependency (not the system time)."""
    fixed = date(2026, 3, 10)
    set_today(client, fixed)
    return fixed
