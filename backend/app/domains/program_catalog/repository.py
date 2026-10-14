"""
Program catalogue repository — pure data access for schema `program`.
Private to the program_catalog domain; other modules go through
interface.py.

Only verified facts are read: a programme whose facts for the intake are
still a draft is left out entirely. Without a requested intake year each
programme is read at its latest verified intake.

The catalogue is maintained by scripts and changes a few times a year,
so each intake's read is cached for the life of the process.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from app.adapters.program_db_adapter import program_db

FACT_COLUMNS = (
    "intake_months", "study_modes", "duration_ft_months", "duration_pt_months", "max_candidature_months",
    "course_count", "total_credits", "credit_unit", "capstone", "internship", "application_fee",
    "application_fee_currency", "gmat_gre_policy", "gmat_gre_note", "toefl_ibt_min", "toefl_ibt_band_min",
    "ielts_min", "ielts_sub_min", "english_waiver", "work_exp_policy", "work_exp_min_years",
    "programming_prereq", "background_requirement", "stem_designated", "cohort_size", "notes",
)

_PROGRAMS_SQL = f"""
    select p.program_id, p.name, p.short_name, p.faculty, p.degree_type, p.category, p.is_target,
           p.aliases, p.official_url, p.delivery, p.summary,
           u.university_id, u.name as university_name, u.short_name as university_short_name,
           u.aliases as university_aliases, u.city, u.country_code, d.name as country_name,
           f.intake_year, f.verified_at, {', '.join('f.' + c for c in FACT_COLUMNS)}
      from program.programs p
      join program.universities u using (university_id)
      join program.destinations d using (country_code)
      join lateral (
          select * from program.facts f
           where f.program_id = p.program_id and f.data_status = 'verified'
             and (%s::smallint is null or f.intake_year = %s::smallint)
           order by f.intake_year desc
           limit 1
      ) f on true
     where p.status = 'active'
     order by p.is_target desc, p.program_id
"""

_cache: dict[int | None, list[dict]] = {}
_cache_lock = threading.Lock()


def _plain(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _row(row: dict) -> dict:
    return {key: _plain(value) for key, value in row.items()}


def _for_intake(rows: list[dict], intakes: dict[str, int]) -> dict[str, list[dict]]:
    """Rows grouped by programme, keeping only the programme's chosen intake."""
    grouped: dict[str, list[dict]] = {pid: [] for pid in intakes}
    for row in rows:
        if intakes.get(row["program_id"]) == row["intake_year"]:
            grouped[row["program_id"]].append(_row(row))
    return grouped


def _funding_applies(row: dict, intake_year: int) -> bool:
    return ((row["valid_from_year"] is None or row["valid_from_year"] <= intake_year)
            and (row["valid_to_year"] is None or row["valid_to_year"] >= intake_year))


def _load(intake_year: int | None) -> list[dict]:
    programs = [_row(r) for r in program_db.fetch_all_dict(_PROGRAMS_SQL, (intake_year, intake_year))]
    if not programs:
        return []
    ids = [p["program_id"] for p in programs]
    universities = sorted({p["university_id"] for p in programs})
    intakes = {p["program_id"]: p["intake_year"] for p in programs}

    fees = _for_intake(program_db.fetch_all_dict(
        """select program_id, intake_year, student_category, amount, currency, basis, includes_tax,
                  note, source_url, quote
             from program.fees where program_id = any(%s)
            order by program_id, student_category""", (ids,)), intakes)
    deadlines = _for_intake(program_db.fetch_all_dict(
        """select program_id, intake_year, round_no, applicant_category, round_label, opens_on, closes_on,
                  source_url
             from program.deadlines where program_id = any(%s)
            order by program_id, round_no, applicant_category""", (ids,)), intakes)
    sources = _for_intake(program_db.fetch_all_dict(
        """select program_id, intake_year, field_key, source_url, quote, role, note
             from program.fact_sources where program_id = any(%s)
            order by program_id, field_key, role desc""", (ids,)), intakes)
    funding_rows = program_db.fetch_all_dict(
        """select f.funding_id, f.program_id, f.university_id, f.name, f.kind, f.amount_kind, f.amount,
                  f.currency, f.percent, f.eligible_categories, f.bond_required, f.conditions,
                  f.valid_from_year, f.valid_to_year, f.source_url
             from program.funding f
            where f.program_id = any(%s) or f.university_id = any(%s)
            order by f.funding_id""", (ids, universities))
    curriculum_rows = program_db.fetch_all_dict(
        """select program_id, skill_id, coverage, evidence_courses, source_url
             from program.curriculum_areas where program_id = any(%s)
            order by program_id, skill_id""", (ids,))

    result = []
    for p in programs:
        pid = p["program_id"]
        by_field: dict[str, list[dict]] = {}
        for s in sources[pid]:
            by_field.setdefault(s["field_key"], []).append(
                {k: s[k] for k in ("source_url", "quote", "role", "note")})
        result.append({
            **{k: p[k] for k in ("program_id", "name", "short_name", "faculty", "degree_type", "category",
                                 "is_target", "aliases", "official_url", "delivery", "summary",
                                 "intake_year", "verified_at")},
            "university": {
                "university_id": p["university_id"], "name": p["university_name"],
                "short_name": p["university_short_name"], "aliases": p["university_aliases"],
                "city": p["city"], "country_code": p["country_code"], "country_name": p["country_name"],
            },
            "facts": {c: p[c] for c in FACT_COLUMNS if p[c] not in (None, [])},
            "sources": by_field,
            "fees": [{k: v for k, v in f.items() if k not in ("program_id", "intake_year")} for f in fees[pid]],
            "deadlines": [{k: v for k, v in d.items() if k not in ("program_id", "intake_year")} for d in deadlines[pid]],
            "funding": [
                {k: v for k, v in _row(f).items() if k not in ("program_id", "university_id")}
                for f in funding_rows
                if (f["program_id"] == pid or f["university_id"] == p["university_id"])
                and _funding_applies(f, p["intake_year"])
            ],
            "curriculum": [
                {k: v for k, v in _row(c).items() if k != "program_id"}
                for c in curriculum_rows if c["program_id"] == pid
            ],
        })
    return result


def list_programs(intake_year: int | None = None) -> list[dict]:
    """Every active programme with verified facts, NUS's MSc DFT first.
    `intake_year`: read that intake only (a programme without verified
    facts for it is left out); None reads each at its latest verified
    intake. See interface.py for the shape."""
    if intake_year not in _cache:
        with _cache_lock:
            if intake_year not in _cache:
                _cache[intake_year] = _load(intake_year)
    return _cache[intake_year]
