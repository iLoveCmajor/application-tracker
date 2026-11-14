"""The storage interface the services depend on.

`SqlRepository` (repositories/sql.py) implements it with SQLAlchemy. Services
depend only on this protocol, never on SQLAlchemy.
"""

from contextlib import AbstractContextManager
from typing import Protocol


class Repository(Protocol):
    def transaction(self) -> AbstractContextManager[None]:
        """All writes inside commit together or not at all. Nested calls join the outer one."""
        ...
