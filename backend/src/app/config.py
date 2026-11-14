"""Settings, read from environment variables only (see _docs/specs.md, "Stack and operations")."""

import os
from pathlib import Path

# A file next to wherever the API is started (backend/ with `make dev-api`). Any
# SQLAlchemy URL works, e.g. postgresql+psycopg://user:pass@localhost/tracker.
DEFAULT_DATABASE_URL = "sqlite:///./tracker.db"


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def app_version() -> str:
    """APP_VERSION, else the commit Render deploys (RENDER_GIT_COMMIT), else "dev"."""
    return os.environ.get("APP_VERSION") or os.environ.get("RENDER_GIT_COMMIT") or "dev"


def seed_demo_data() -> bool:
    """SEED_DEMO_DATA: "true", "1" or "yes" (any case) seeds an empty database on start."""
    return os.environ.get("SEED_DEMO_DATA", "").strip().lower() in {"true", "1", "yes"}


def static_dir() -> Path | None:
    """STATIC_DIR: the built frontend (frontend/dist) to serve at /. Unset: API only.

    The Docker image sets it; `make dev` leaves it unset and Vite serves the UI.
    """
    value = os.environ.get("STATIC_DIR")
    return Path(value) if value else None
