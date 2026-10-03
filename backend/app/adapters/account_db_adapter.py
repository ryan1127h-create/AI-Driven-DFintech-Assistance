"""
Schema `account` (accounts, user_settings), owned by
app/domains/auth/repository.py. Shares the connection pool with every other
schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

account_db = SchemaDB("account", pool)
