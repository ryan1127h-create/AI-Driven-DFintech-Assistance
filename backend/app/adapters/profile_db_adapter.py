"""
Schema `profile` (field dictionary, values, events, conflicts, consents,
derived labels, CV documents), owned by app/domains/profile/repository.py.
Shares the connection pool with every other schema adapter — see
postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

profile_db = SchemaDB("profile", pool)
