"""
Public interface of the program_catalog domain — the only module other
modules are allowed to import from app.domains.program_catalog.

Each programme from list_programs() is a plain dict:
    program_id, name, short_name, faculty, degree_type, category,
    is_target (NUS MSc DFT), aliases, official_url, delivery, summary,
    intake_year, verified_at,
    university: {university_id, name, short_name, aliases, city,
                 country_code, country_name},
    facts:      {column: value} — only the facts on file (repository.FACT_COLUMNS),
    sources:    {field_key: [{source_url, quote, role, note}]} — role
                'primary' is the page the value follows, 'conflicting' one
                that says otherwise (note: how it was decided),
    fees:       [{student_category, amount, currency, basis, includes_tax, note, source_url, quote}],
    deadlines:  [{round_no, applicant_category, round_label, opens_on, closes_on, source_url}],
    funding:    [{funding_id, name, kind, amount_kind, amount, currency, percent,
                  eligible_categories (None: the source doesn't say), bond_required,
                  conditions, valid_from_year, valid_to_year, source_url}],
    curriculum: [{skill_id, coverage, evidence_courses, source_url}] — a
                skill with no entry is unknown, not untaught.

Usage:
    from app.domains.program_catalog.interface import list_programs
    programs = list_programs()
"""

from __future__ import annotations

from app.domains.program_catalog.repository import list_programs

__all__ = ["list_programs"]
