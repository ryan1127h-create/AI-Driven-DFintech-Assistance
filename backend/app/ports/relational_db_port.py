"""
Contract for "a database that can run parameterized SQL and return rows".
A repository depends on this shape rather than a specific driver, so
swapping the underlying driver — or the database engine itself — only
touches whichever adapter implements this port.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, Sequence


class DBSession(Protocol):
    """The statement-running half of the port. Called on the port itself,
    each statement commits on its own; called on the session yielded by
    RelationalDBPort.transaction(), they commit (or roll back) together."""

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        """Runs a SELECT expected to return at most one row."""
        ...

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[tuple]:
        """Runs a SELECT and returns every matching row."""
        ...

    def fetch_one_dict(self, query: str, params: Sequence[Any] = ()) -> dict | None:
        """fetch_one, with the row keyed by column name."""
        ...

    def fetch_all_dict(self, query: str, params: Sequence[Any] = ()) -> list[dict]:
        """fetch_all, with each row keyed by column name."""
        ...

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        """Runs a statement whose returned rows (if any) aren't needed."""
        ...

    def execute_returning(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        """Runs an INSERT/UPDATE ... RETURNING statement and returns the
        single row it produced."""
        ...


class RelationalDBPort(DBSession, Protocol):
    def transaction(self) -> AbstractContextManager[DBSession]:
        """A session whose statements commit together when the block exits
        normally and roll back together if it raises."""
        ...
