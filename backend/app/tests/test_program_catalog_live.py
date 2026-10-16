"""The programme catalogue read against the live database: the SQL runs
against the current `program` schema and every programme comes back with
its facts and sources, NUS's MSc DFT first. Read-only.

    RUN_LIVE_DB_TESTS=1 pytest app/tests/test_program_catalog_live.py
"""

from __future__ import annotations

import os

import pytest

from app.domains.program_catalog import repository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(repository, "_cache", {})


def test_catalogue_reads_with_dft_first():
    programs = repository.list_programs()
    assert programs and programs[0]["program_id"] == "nus_msc_dft"
    assert sum(p["is_target"] for p in programs) == 1
    for p in programs:
        assert p["facts"], p["program_id"]
        missing = [k for k in p["facts"] if k not in p["sources"]
                   and k not in ("credit_unit", "application_fee_currency")]
        assert missing == [], (p["program_id"], missing)


def test_unknown_intake_reads_nothing():
    assert repository.list_programs(2035) == []
