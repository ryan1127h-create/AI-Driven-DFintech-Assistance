"""
Schema `sis` (academic records, course enrollments, applications,
programmes), owned by app/domains/sis/repository.py. Shares the connection
pool with every other schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

sis_db = SchemaDB("sis", pool)
