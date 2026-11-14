from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    """Bring the database schema up to `revision` (the app runs this on start)."""
    _run(engine, lambda config: command.upgrade(config, revision))


def downgrade(engine: Engine, revision: str = "base") -> None:
    _run(engine, lambda config: command.downgrade(config, revision))


def _run(engine: Engine, action: Callable[[Config], None]) -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        action(config)
