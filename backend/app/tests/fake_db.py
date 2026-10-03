"""In-memory stand-in for RelationalDBPort used by the repository tests:
records every statement (and whether it ran inside transaction()), and
answers reads from a queue of canned results, so a test can assert on the
exact SQL/params a repository function issues without a database."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any


class FakeDB:
    def __init__(self, results: list[Any] | None = None, fail_on: str | None = None) -> None:
        # Popped in order by every call that returns something; an empty
        # queue answers None (one-row calls) or [] (many-row calls).
        self.results = list(results or [])
        # Raise when a statement containing this text is executed.
        self.fail_on = fail_on
        self.calls: list[dict] = []
        self.events: list[str] = []  # begin / commit / rollback
        self._in_tx = False

    def _record(self, method: str, query: str, params) -> None:
        self.calls.append({"method": method, "sql": " ".join(query.split()), "params": list(params), "in_tx": self._in_tx})
        if self.fail_on and self.fail_on in query:
            raise RuntimeError(f"forced failure on {self.fail_on!r}")

    def _next(self, default):
        return self.results.pop(0) if self.results else default

    def fetch_one(self, query, params=()):
        self._record("fetch_one", query, params)
        return self._next(None)

    def fetch_all(self, query, params=()):
        self._record("fetch_all", query, params)
        return self._next([])

    def fetch_one_dict(self, query, params=()):
        self._record("fetch_one_dict", query, params)
        return self._next(None)

    def fetch_all_dict(self, query, params=()):
        self._record("fetch_all_dict", query, params)
        return self._next([])

    def execute(self, query, params=()):
        self._record("execute", query, params)

    def execute_returning(self, query, params=()):
        self._record("execute_returning", query, params)
        return self._next(None)

    @contextmanager
    def transaction(self):
        self.events.append("begin")
        self._in_tx = True
        try:
            yield self
        except BaseException:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")
        finally:
            self._in_tx = False

    def sql(self, i: int) -> str:
        return self.calls[i]["sql"]
