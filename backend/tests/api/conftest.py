import pytest


@pytest.fixture(autouse=True)
def _clean_database(empty_tables: None) -> None:
    """Every API test starts with empty tables."""
