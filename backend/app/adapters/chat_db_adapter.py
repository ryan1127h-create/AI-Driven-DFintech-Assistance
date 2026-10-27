"""
Schema `chat` (conversations and their archived messages), owned by
app/domains/conversation/repository.py. Shares the connection pool with
every other schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

chat_db = SchemaDB("chat", pool)
