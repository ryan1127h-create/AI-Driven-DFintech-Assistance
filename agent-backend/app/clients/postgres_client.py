"""
Lazy Postgres connection helper, shared by every repository that talks to a
Supabase/Postgres database (the conversation-storage project and the
read-only knowledge-base project use separate DSNs, so each repository
holds its own LazyPostgresConnection instance).
"""

from __future__ import annotations

import threading

import psycopg


class LazyPostgresConnection:
    """Opens a connection on first use and transparently reconnects if the
    underlying connection was closed (e.g. after an idle timeout).

    The check-then-connect below is guarded by a lock because this is
    called from multiple threads concurrently: app/modules/chatbot/agents/
    supervisor.py::dispatch_node runs several specialist branches (each of
    which may read through this same connection, directly or via
    knowledge_repository/profile.repository) in a thread pool. Without the
    lock, a burst of concurrent first-uses (cold start, or right after an
    idle-timeout reconnect) can each pass the None/closed check before any
    of them finishes connecting, leaking one connection object per race —
    harmless for the winning threads' results, but a real
    connection-pool-exhaustion risk under bursty concurrent load."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._lock = threading.Lock()

    def get(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            with self._lock:
                if self._conn is None or self._conn.closed:
                    self._conn = psycopg.connect(self._dsn, connect_timeout=5)
        return self._conn
