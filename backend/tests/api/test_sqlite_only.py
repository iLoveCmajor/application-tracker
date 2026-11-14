"""AC-15.1/15.2: the API suite runs on its own temporary SQLite file, whatever the environment says."""

import pytest
from sqlalchemy import Engine


def test_ac15_2_api_suite_uses_temporary_sqlite(
    engine: Engine, tmp_path_factory: pytest.TempPathFactory
) -> None:
    assert engine.dialect.name == "sqlite"
    assert engine.url.database is not None
    assert engine.url.database.startswith(str(tmp_path_factory.getbasetemp()))
