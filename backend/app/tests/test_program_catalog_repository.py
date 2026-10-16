"""domains/program_catalog/repository.py: only verified facts are read, a
programme's related rows are kept for its chosen intake only, funding
outside its valid years is dropped, and numbers come back as plain ints
and floats — against FakeDB, no database."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domains.program_catalog import repository
from app.tests.fake_db import FakeDB


def _program(pid, university, intake, is_target=False, **facts):
    row = {
        "program_id": pid, "name": pid, "short_name": pid, "faculty": None, "degree_type": "MSc",
        "category": "fintech", "is_target": is_target, "aliases": [], "official_url": "u", "delivery": "on_campus",
        "summary": None, "university_id": university, "university_name": university.upper(),
        "university_short_name": university.upper(), "university_aliases": [], "city": "C",
        "country_code": "SG", "country_name": "Singapore", "intake_year": intake, "verified_at": None,
    }
    row.update({c: None for c in repository.FACT_COLUMNS})
    row.update(facts)
    return row


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(repository, "program_db", fake)
    monkeypatch.setattr(repository, "_cache", {})
    return fake


def _results(programs, fees=(), deadlines=(), sources=(), funding=(), curriculum=()):
    return [list(programs), list(fees), list(deadlines), list(sources), list(funding), list(curriculum)]


def test_reads_verified_facts_only(db):
    repository.list_programs()
    assert "f.data_status = 'verified'" in db.sql(0)
    assert db.calls[0]["params"] == [None, None]


def test_related_rows_follow_each_programmes_intake(db):
    db.results = _results(
        [_program("dft", "nus", 2027, True, application_fee=Decimal("109.00"), ielts_min=Decimal("6.0")),
         _program("ust", "hkust", 2026)],
        fees=[{"program_id": "dft", "intake_year": 2027, "student_category": "all", "amount": Decimal("76409.00"),
               "currency": "SGD", "basis": "programme", "includes_tax": True, "note": None, "source_url": "u", "quote": "q"},
              {"program_id": "dft", "intake_year": 2026, "student_category": "all", "amount": Decimal("74120.00"),
               "currency": "SGD", "basis": "programme", "includes_tax": True, "note": None, "source_url": "u", "quote": "q"}],
        sources=[{"program_id": "dft", "intake_year": 2027, "field_key": "ielts_min", "source_url": "a",
                  "quote": "q1", "role": "primary", "note": None},
                 {"program_id": "dft", "intake_year": 2027, "field_key": "ielts_min", "source_url": "b",
                  "quote": "q2", "role": "conflicting", "note": "n"}],
    )
    dft, ust = repository.list_programs()
    assert dft["is_target"] and dft["intake_year"] == 2027
    assert [f["amount"] for f in dft["fees"]] == [76409]
    assert dft["facts"] == {"application_fee": 109, "ielts_min": 6.0}
    assert [s["role"] for s in dft["sources"]["ielts_min"]] == ["primary", "conflicting"]
    assert ust["fees"] == [] and ust["sources"] == {}
    assert dft["university"]["university_id"] == "nus"


def test_funding_covers_programme_and_university_within_valid_years(db):
    db.results = _results(
        [_program("dft", "nus", 2027, True)],
        funding=[
            {"funding_id": "own", "program_id": "dft", "university_id": None, "valid_from_year": None,
             "valid_to_year": None, "amount": Decimal("45000.00"), "percent": None},
            {"funding_id": "uni", "program_id": None, "university_id": "nus", "valid_from_year": 2024,
             "valid_to_year": 2028, "amount": None, "percent": Decimal("40.00")},
            {"funding_id": "expired", "program_id": "dft", "university_id": None, "valid_from_year": 2024,
             "valid_to_year": 2026, "amount": None, "percent": None},
            {"funding_id": "other", "program_id": "x", "university_id": None, "valid_from_year": None,
             "valid_to_year": None, "amount": None, "percent": None},
        ],
    )
    [dft] = repository.list_programs()
    assert [f["funding_id"] for f in dft["funding"]] == ["own", "uni"]
    assert dft["funding"][0]["amount"] == 45000 and dft["funding"][1]["percent"] == 40


def test_no_programmes_reads_nothing_else(db):
    assert repository.list_programs(2030) == []
    assert len(db.calls) == 1
    assert db.calls[0]["params"] == [2030, 2030]


def test_each_intake_is_read_once(db):
    db.results = _results([_program("dft", "nus", 2027, True)])
    repository.list_programs()
    calls = len(db.calls)
    repository.list_programs()
    assert len(db.calls) == calls
