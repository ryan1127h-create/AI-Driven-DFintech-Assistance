"""
Postgres adapter for RelationalDBPort, backed by a lazily-opened,
thread-safe connection to the conversation-storage database (the `student`
schema — users, profiles, checklist items, conversations, ...). One
instance (`conversation_db`, below) is shared by every domain that reads
from this database, rather than each domain opening its own connection.
"""

from __future__ import annotations

import threading
from typing import Any, Sequence

import psycopg

from app.core.config import settings
from app.ports.relational_db_port import RelationalDBPort


class _LazyConnection:
    """Opens a connection on first use and transparently reconnects if the
    underlying connection was closed (e.g. after an idle timeout).

    The check-then-connect below is guarded by a lock because several
    domains' handlers can run concurrently on worker threads and share this
    one connection object — without the lock, a burst of concurrent
    first-uses could each pass the None/closed check before any of them
    finishes connecting, leaking one connection object per race."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._lock = threading.Lock()

    def get(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            with self._lock:
                if self._conn is None or self._conn.closed:
                    self._conn = psycopg.connect(self._dsn, connect_timeout=5)
        return self._conn


class ConversationDBAdapter(RelationalDBPort):
    def __init__(self, dsn: str) -> None:
        self._lazy = _LazyConnection(dsn)

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        conn = self._lazy.get()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        except Exception:
            # A failed query leaves the connection in an aborted-transaction
            # state until it's rolled back — without this, every later call
            # on this same (reused) connection would fail too, not just the
            # one that actually errored.
            conn.rollback()
            raise

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[tuple]:
        conn = self._lazy.get()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        except Exception:
            conn.rollback()
            raise

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        conn = self._lazy.get()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute_returning(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        conn = self._lazy.get()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise


conversation_db = ConversationDBAdapter(settings.conversation_database_url)
