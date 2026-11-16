from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.pool import StaticPool


def create_db_engine(url: str) -> Engine:
    """An engine for any SQLAlchemy URL, with the SQLite settings the app relies on.

    Every engine hides bound parameters (application fields) from its error messages, so a
    failing statement never puts them into a log line (#25).
    """
    if make_url(url).get_backend_name() == "sqlite":
        return _sqlite_engine(url)
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def _sqlite_engine(url: str) -> Engine:
    database = make_url(url).database
    in_memory = database in (None, "", ":memory:")
    engine = create_engine(
        url,
        # FastAPI may open and use a connection on different threads.
        connect_args={"check_same_thread": False, "timeout": 30},
        # An in-memory database exists per connection, so share a single one.
        poolclass=StaticPool if in_memory else None,
        hide_parameters=True,
    )

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_connection: Any, _record: Any) -> None:
        # Let SQLAlchemy issue BEGIN itself (below) instead of the sqlite3 module.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
        cursor.close()

    @event.listens_for(engine, "begin")
    def on_begin(connection: Connection) -> None:
        # Take the write lock up front. SQLite has no SELECT … FOR UPDATE, and a
        # deferred transaction that later upgrades to a writer can fail with
        # "database is locked" under concurrent requests.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def is_reachable(engine: Engine) -> bool:
    """True when the database answers `SELECT 1` (the /ready check)."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
