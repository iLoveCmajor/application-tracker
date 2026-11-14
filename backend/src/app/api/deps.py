from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, Request

from app.repositories.base import Repository
from app.repositories.sql import open_repository
from app.services import clock


def get_repo(request: Request) -> Iterator[Repository]:
    """One connection per request; anything not committed is rolled back on close."""
    with open_repository(request.app.state.engine) as repo:
        yield repo


Repo = Annotated[Repository, Depends(get_repo)]


def get_today() -> date:
    """The date the business rules see as today. Tests override this dependency to fix it."""
    return clock.today()


Today = Annotated[date, Depends(get_today)]
