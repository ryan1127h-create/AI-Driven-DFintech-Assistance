"""
The one PostgreSQL connection pool, and SchemaDB — the RelationalDBPort
every schema adapter (account_db, profile_db, sis_db, chat_db,
knowledge_db) is an instance of. All schemas live in one database behind
one DATABASE_URL, so they share this pool; the per-schema adapters exist
to make ownership explicit — each repository imports only its own schema's
adapter, and its SQL names only that schema (enforced by
app/tests/test_architecture.py).

Every pooled connection runs in autocommit mode, so a plain fetch_*/execute
call is its own transaction and never leaves a connection sitting idle
inside an open one. Work that must be atomic across several statements goes
through `transaction()`, which pins one connection for the whole block and
wraps it in a real BEGIN/COMMIT (a real one, not a savepoint, precisely
because the connection is in autocommit mode — see psycopg's
Connection.transaction()).

`prepare_threshold=None` disables server-side prepared statements: the
DATABASE_URL points at Supabase's transaction-mode pooler (port 6543),
which hands each transaction a possibly different backend, so a statement
prepared on one would be missing — or already exist — on the next.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings
from app.ports.relational_db_port import RelationalDBPort


class _Session:
    """The fetch/execute methods of RelationalDBPort, run against one
    already-checked-out connection. Used directly as the object yielded by
    transaction(); SchemaDB reuses it per call too, so the two can't drift
    apart."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetch_one_dict(self, query: str, params: Sequence[Any] = ()) -> dict | None:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def fetch_all_dict(self, query: str, params: Sequence[Any] = ()) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        with self._conn.cursor() as cur:
            cur.execute(query, params)

    def execute_returning(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


class PostgresPool:
    """Lazily opened on first use."""

    def __init__(self, dsn: str, max_size: int) -> None:
        self._dsn = dsn
        self._max_size = max_size
        self._pool: ConnectionPool | None = None
        # Guards the first open: handlers run concurrently on worker
        # threads, and without the lock a burst of first uses could each
        # build (and leak) their own pool.
        self._lock = threading.Lock()

    def _get(self) -> ConnectionPool:
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    self._pool = ConnectionPool(
                        self._dsn,
                        min_size=1,
                        max_size=self._max_size,
                        kwargs={"autocommit": True, "prepare_threshold": None, "connect_timeout": 5},
                        # Supabase's pooler drops idle connections; check on
                        # checkout so a dead one is replaced instead of
                        # failing the caller's query.
                        check=ConnectionPool.check_connection,
                        open=True,
                    )
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        with self._get().connection() as conn:
            yield conn

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None


class SchemaDB(RelationalDBPort):
    """RelationalDBPort for one schema, over the shared pool. `schema` is
    the schema this adapter's owner may query."""

    def __init__(self, schema: str, pool: PostgresPool) -> None:
        self.schema = schema
        self._pool = pool

    @contextmanager
    def _session(self) -> Iterator[_Session]:
        with self._pool.connection() as conn:
            yield _Session(conn)

    def fetch_one(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        with self._session() as s:
            return s.fetch_one(query, params)

    def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[tuple]:
        with self._session() as s:
            return s.fetch_all(query, params)

    def fetch_one_dict(self, query: str, params: Sequence[Any] = ()) -> dict | None:
        with self._session() as s:
            return s.fetch_one_dict(query, params)

    def fetch_all_dict(self, query: str, params: Sequence[Any] = ()) -> list[dict]:
        with self._session() as s:
            return s.fetch_all_dict(query, params)

    def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        with self._session() as s:
            s.execute(query, params)

    def execute_returning(self, query: str, params: Sequence[Any] = ()) -> tuple | None:
        with self._session() as s:
            return s.execute_returning(query, params)

    @contextmanager
    def transaction(self) -> Iterator[_Session]:
        """All statements run on the yielded session commit together when
        the block exits normally, and roll back together if it raises."""
        with self._pool.connection() as conn:
            with conn.transaction():
                yield _Session(conn)


pool = PostgresPool(settings.database_url, settings.db_pool_max_size)
