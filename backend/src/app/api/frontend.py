"""Serves the built frontend (frontend/dist) at / when STATIC_DIR is set, as the Docker image does.

Registered after every other route, so /api/v1/*, /health, /ready and /docs keep their own
handlers. Anything under /api stays a JSON 404 in the error format, never index.html.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR has no index.html: {root}")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        # A missing file (an asset name) is a 404; any other path is a page of the app.
        if Path(path).suffix:
            raise StarletteHTTPException(status_code=404)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
