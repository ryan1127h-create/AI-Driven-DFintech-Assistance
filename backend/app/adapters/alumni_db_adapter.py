"""
Schema `alumni` (the alumni directory and students' connection requests),
owned by app/domains/alumni/repository.py. Shares the connection pool with
every other schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

alumni_db = SchemaDB("alumni", pool)
