import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import Engine

from app.api import applications, followups, health, stats
from app.api.errors import register_error_handlers
from app.api.frontend import mount_frontend
from app.config import app_version, database_url, seed_demo_data, static_dir
from app.db.engine import create_db_engine
from app.db.migrate import upgrade
from app.repositories.sql import open_repository
from app.services import clock
from app.services.seed import seed_if_empty

API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


def create_app(
    engine: Engine | None = None,
    *,
    migrate: bool = True,
    seed: bool = False,
    frontend_dir: Path | None = None,
) -> FastAPI:
    """Build the app on `engine`, or on DATABASE_URL (default: a local SQLite file).

    With `migrate`, pending Alembic migrations run on startup, before any request is served.
    With `seed`, an empty database then gets the invented demo applications.
    With `frontend_dir`, the built frontend is served at / (see api/frontend.py).
    """
    owns_engine = engine is None
    db = engine if engine is not None else create_db_engine(database_url())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if migrate:
            upgrade(db)
        if seed:
            with open_repository(db) as repo:
                created = seed_if_empty(repo, clock.today())
            logger.info("Seeded %d demo applications", created)
        yield
        if owns_engine:
            db.dispose()

    app = FastAPI(title="Application Tracker API", version=app_version(), lifespan=lifespan)
    app.state.engine = db
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(applications.router, prefix=API_PREFIX)
    app.include_router(followups.router, prefix=API_PREFIX)
    app.include_router(stats.router, prefix=API_PREFIX)
    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)  # last: its catch-all must not shadow the routes above
    return app


app = create_app(seed=seed_demo_data(), frontend_dir=static_dir())
