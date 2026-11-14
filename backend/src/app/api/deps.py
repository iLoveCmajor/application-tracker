from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.repositories.base import Repository
from app.repositories.sql import open_repository


def get_repo(request: Request) -> Iterator[Repository]:
    """One connection per request; anything not committed is rolled back on close."""
    with open_repository(request.app.state.engine) as repo:
        yield repo


Repo = Annotated[Repository, Depends(get_repo)]
