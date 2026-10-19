"""
Cross-schema access for the staff console, owned by
app/domains/admin/repository.py. Unlike the per-schema adapters, the admin
console reads (and edits) rows across account, profile, sis, chat,
knowledge and program, so it is the one sanctioned exception to the
"each owner queries only its own schema" rule (see
tests/test_architecture.py). Shares the connection pool with every other
schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

reporting_db = SchemaDB("admin_reporting", pool)
