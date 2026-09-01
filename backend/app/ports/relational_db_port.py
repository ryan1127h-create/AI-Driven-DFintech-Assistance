"""
Contract for "a database that can run parameterized SQL and return rows".
A repository depends on this shape rather than a specific driver, so
swapping the underlying driver — or the database engine itself — only
touches whichever adapter implements this port.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence


class RelationalDBPort(Protocol):
    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        """Runs a SELECT expected to return at most one row."""
        ...

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[tuple]:
        """Runs a SELECT and returns every matching row."""
        ...

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        """Runs a statement whose returned rows (if any) aren't needed, and
        commits."""
        ...

    def execute_returning(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        """Runs an INSERT/UPDATE ... RETURNING statement, commits, and
        returns the single row it produced."""
        ...
