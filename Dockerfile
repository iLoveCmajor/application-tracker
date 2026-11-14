# Application Tracker: one image serving the API and the built frontend on port 8080.

# ---- frontend: build the static UI ------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- app: Python + uv, no node ----------------------------------------------
FROM python:3.14-slim AS app

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    PORT=8080 \
    LOG_LEVEL=info

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable

COPY --from=frontend /frontend/dist ./static

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/ready')"

# Migrations (and the demo seed, if SEED_DEMO_DATA is true) run in the app's startup.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --log-level \"$LOG_LEVEL\""]
