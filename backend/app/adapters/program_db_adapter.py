"""
Schema `program` (the programme catalogue: universities, programmes and
their per-intake facts, fees, deadlines, funding and curriculum
coverage), owned by app/domains/program_catalog/repository.py. Shares the
connection pool with every other schema adapter — see postgres_pool.py.
"""

from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

program_db = SchemaDB("program", pool)
