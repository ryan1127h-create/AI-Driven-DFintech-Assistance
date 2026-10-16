"""
S2 — builds the domain's ComparisonInput from what prefetch gathered and
what S1 parsed. Pure: no reads.

Programmes named: S1's ids, else (when parsing failed or found none) the
classifier's program_hints resolved by name (programs.py).

Which mode runs, and for which programmes:

    compare  MSc DFT against the other programmes named; with none named,
             the ones the previous comparison covered ("and the fees?"),
             then the profile's competing_programs; with still none, an
             explore of FinTech programmes, offered to choose from
    detail   the one programme named (MSc DFT included); with several
             named, a compare; with none, the previous turn's single
             programme, else a compare as above
    explore  the catalogue filtered by the stated conditions

No mode stated: other programmes named compare, only MSc DFT named is a
detail of it, conditions alone explore, nothing at all compares as above.
At most three programmes are compared; each fallback adds a note saying
what ran instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.tools.specialist.program_comparison.s1_understanding.schema import ParsedComparisonRequest
from app.tools.specialist.program_comparison.s2_assembly import programs as program_names
from app.tools.specialist.program_comparison.s2_assembly.prefetched import Prefetched

_MAX_SUBJECTS = 3
_TEST_KEYS = ("GRE", "GMAT", "GATE", "TOEFL", "IELTS")
_TERM = re.compile(r"^AY(\d{4})/\d{2} Sem[12]$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_NOTES = {
    "nothing_to_compare": (
        "No programme to compare with MSc DFT was named, so here are the FinTech programmes in the comparison "
        "data; name one or more to compare them in detail."
    ),
    "too_many": "Only three programmes can be compared at a time, so this covers {names}.",
    "unmatched": "{names} isn't in the comparison data, which covers {available}.",
    "unmatched_instead": (
        "{names} isn't in the comparison data, so here are the FinTech programmes it does cover; name one or "
        "more to compare them with MSc DFT in detail."
    ),
    "parse_failed": "Your message couldn't be fully made out, so this works from the programmes it names.",
}


@dataclass(frozen=True)
class Built:
    report: dict
    notes: tuple[str, ...]
    # What ran instead of what was asked: "explore_instead_of_compare", or None.
    fallback: str | None = None


def _bool(value) -> bool | None:
    return value if isinstance(value, bool) else None


def _tests(items) -> list[dict]:
    tests = []
    for item in items or []:
        if not isinstance(item, dict) or item.get("key") not in _TEST_KEYS:
            continue
        score = item.get("score")
        test_date = item.get("test_date")
        tests.append({
            "key": item["key"],
            "score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
            "test_date": test_date if isinstance(test_date, str) and _DATE.fullmatch(test_date) else None,
        })
    return tests


def _intake_year(term) -> int | None:
    match = _TERM.fullmatch(term) if isinstance(term, str) else None
    return int(match.group(1)) if match else None


def _applicant(prefetched: Prefetched, parsed: ParsedComparisonRequest) -> dict:
    f = prefetched.facts
    role_tag = parsed.role or prefetched.profile_role
    role = next((r for r in prefetched.role_catalog if r["tag"] == role_tag), None)
    applicant = {
        "residency": f.get("residency_category"),
        "is_nus_alumnus": _bool(f.get("is_nus_alumnus")),
        "english_medium_degree": _bool(f.get("english_medium_degree")),
        "tests": _tests(f.get("admission_tests")),
        "total_work_years": f.get("total_work_years"),
        "decision_factors": [v for v in f.get("decision_factors") or [] if isinstance(v, str)],
        "intake_year": parsed.intake_year or _intake_year(f.get("intake_term")),
        "target_role": role["name"] if role else None,
        "target_skills": list(role["required_skills"]) if role else [],
    }
    return {k: v for k, v in applicant.items() if v not in (None, [])}


def _names(prefetched: Prefetched, ids: list[str]) -> str:
    by_id = {p["program_id"]: p for p in prefetched.programs}
    return ", ".join(f"{by_id[i]['university']['short_name']} {by_id[i]['short_name']}" for i in ids)


def build_report(
    prefetched: Prefetched, parsed: ParsedComparisonRequest, mode_hint: str | None, program_hints: list[str],
    today: date, user_id: str | None, previous_programs: list[str] | tuple[str, ...] = (),
) -> Built:
    notes: list[str] = []
    target = prefetched.target_id
    known = {p["program_id"] for p in prefetched.programs}

    named, unmatched = list(parsed.programs), list(parsed.unmatched_programs)
    if not named and program_hints:
        named, from_hints = program_names.resolve(program_hints, prefetched.programs)
        unmatched = list(dict.fromkeys([*unmatched, *from_hints]))
    if parsed.parse_failed:
        notes.append(_NOTES["parse_failed"])
    others = [p for p in named if p != target]
    has_conditions = bool(parsed.countries or parsed.study_mode or parsed.categories)
    mode = mode_hint or parsed.mode
    if mode is None:
        mode = "compare" if others else "detail" if target in named else "explore" if has_conditions else "compare"
    if mode == "detail" and len(named) > 1:
        mode = "compare"
    if mode == "detail" and not named:
        previous = [p for p in previous_programs if p in known]
        if len(previous) == 1:
            named = previous
        else:
            mode = "compare"

    subjects: list[str] = []
    fallback = None
    conditions = {"countries": parsed.countries, "study_mode": parsed.study_mode, "categories": parsed.categories}
    if mode == "detail":
        subjects = named[:1]
    elif mode == "compare":
        subjects = others
        if not subjects:
            subjects = [p for p in previous_programs if p in known and p != target]
        if not subjects:
            competing = [n for n in prefetched.facts.get("competing_programs") or [] if isinstance(n, str)]
            subjects = [p for p in program_names.resolve(competing, prefetched.programs)[0] if p != target]
        if not subjects:
            mode, fallback = "explore", "explore_instead_of_compare"
            conditions = {**conditions, "categories": parsed.categories or ["fintech"]}
            if not unmatched:
                notes.append(_NOTES["nothing_to_compare"])
        elif len(subjects) > _MAX_SUBJECTS:
            subjects = subjects[:_MAX_SUBJECTS]
            notes.append(_NOTES["too_many"].format(names=_names(prefetched, subjects)))

    if unmatched:
        names = ", ".join(unmatched)
        if fallback:
            notes.append(_NOTES["unmatched_instead"].format(names=names))
        else:
            available = "; ".join(f"{p['university']['short_name']} {p['short_name']}" for p in prefetched.programs)
            notes.append(_NOTES["unmatched"].format(names=names, available=available))

    report = {
        "mode": mode,
        "today": today,
        "programs": prefetched.programs,
        "subject_ids": subjects,
        "dimensions": parsed.dimensions,
        "applicant": _applicant(prefetched, parsed),
        "conditions": {k: v for k, v in conditions.items() if v},
    }
    if user_id:
        report["user_id"] = user_id
    return Built(report, tuple(notes), fallback)
