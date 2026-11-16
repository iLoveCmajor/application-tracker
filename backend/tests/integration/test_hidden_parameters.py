"""AC-25.2 on PostgreSQL: a failing statement's error does not carry its bound parameters."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

CANARY = "param-leak-canary-25"


def test_ac25_2_postgres_error_does_not_contain_parameters(engine: Engine) -> None:
    assert engine.hide_parameters is True
    with pytest.raises(DBAPIError) as raised, engine.begin() as connection:
        connection.execute(text("INSERT INTO no_such_table (value) VALUES (:value)"), {"value": CANARY})
    assert "no_such_table" in str(raised.value)
    assert CANARY not in str(raised.value)
    assert CANARY not in repr(raised.value)
