"""
Lazy Postgres connection helper, shared by every repository that talks to a
Supabase/Postgres database (the conversation-storage project and the
read-only knowledge-base project use separate DSNs, so each repository
holds its own LazyPostgresConnection instance).
"""

from __future__ import annotations

import psycopg


class LazyPostgresConnection:
    """Opens a connection on first use and transparently reconnects if the
    underlying connection was closed (e.g. after an idle timeout)."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None

    def get(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn, connect_timeout=5)
        return self._conn
