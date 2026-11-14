"""Settings, read from environment variables only (see _docs/specs.md, "Stack and operations")."""

import os

# A file next to wherever the API is started (backend/ with `make dev-api`). Any
# SQLAlchemy URL works, e.g. postgresql+psycopg://user:pass@localhost/tracker.
DEFAULT_DATABASE_URL = "sqlite:///./tracker.db"


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def app_version() -> str:
    """APP_VERSION, else the commit Render deploys (RENDER_GIT_COMMIT), else "dev"."""
    return os.environ.get("APP_VERSION") or os.environ.get("RENDER_GIT_COMMIT") or "dev"
