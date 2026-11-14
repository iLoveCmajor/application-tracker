"""Alembic environment.

Used both by the CLI (`uv run alembic …`, configured by backend/alembic.ini) and
by `app.db.migrate.upgrade()` at app start, which passes its own connection.
"""

from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy.engine import Connection

from app.config import database_url
from app.db.engine import create_db_engine
from app.db.tables import UTCDateTime, metadata

config = context.config


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    # Write UTCDateTime as its underlying column type so migrations don't import app code.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=metadata,
        # Lets later ALTER-style migrations work on SQLite too.
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url") or database_url(),
        target_metadata=metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        run(connection)
        return
    engine = create_db_engine(config.get_main_option("sqlalchemy.url") or database_url())
    try:
        with engine.begin() as connection:
            run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
