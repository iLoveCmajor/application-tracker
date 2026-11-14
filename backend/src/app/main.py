from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from app.api import applications, followups, health, stats
from app.api.errors import register_error_handlers
from app.config import app_version, database_url
from app.db.engine import create_db_engine
from app.db.migrate import upgrade

API_PREFIX = "/api/v1"


def create_app(engine: Engine | None = None, *, migrate: bool = True) -> FastAPI:
    """Build the app on `engine`, or on DATABASE_URL (default: a local SQLite file).

    With `migrate`, pending Alembic migrations run on startup, before any request is served.
    """
    owns_engine = engine is None
    db = engine if engine is not None else create_db_engine(database_url())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if migrate:
            upgrade(db)
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
    return app


app = create_app()
