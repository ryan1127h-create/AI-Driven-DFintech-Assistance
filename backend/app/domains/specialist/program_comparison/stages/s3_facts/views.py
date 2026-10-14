"""
S3 — lays one catalogue programme out by aspect (policy/dimensions.py),
keeping only the facts on file, each aspect with the pages its facts came
from, and every fact an official page states differently (a 'conflicting'
source) as a Conflict the reply must mention.
"""

from __future__ import annotations

from app.domains.specialist.program_comparison.models import Conflict, ProgramView
from app.domains.specialist.program_comparison.policy.dimensions import FIELD_DIMENSION


def _drop_empty(values: dict) -> dict:
    return {k: v for k, v in values.items() if v not in (None, [], (), "")}


def _facts(program: dict) -> dict[str, dict]:
    f = program["facts"]
    university = program["university"]
    by_dimension = {
        "cost": _drop_empty({
            "fees": [_drop_empty({k: fee.get(k) for k in ("student_category", "amount", "currency", "basis",
                                                            "includes_tax", "note")}) for fee in program["fees"]],
            "application_fee": ({"amount": f["application_fee"], "currency": f.get("application_fee_currency")}
                                if f.get("application_fee") is not None else None),
        }),
        "duration": _drop_empty({
            "full_time_months": f.get("duration_ft_months"), "part_time_months": f.get("duration_pt_months"),
            "max_months": f.get("max_candidature_months"), "courses": f.get("course_count"),
            "credits": f.get("total_credits"), "credit_unit": f.get("credit_unit"),
        }),
        "curriculum": _drop_empty({
            "areas": [_drop_empty({"skill": a["skill_id"], "coverage": a["coverage"],
                                   "courses": list(a.get("evidence_courses") or [])}) for a in program["curriculum"]],
            "capstone": f.get("capstone"), "internship": f.get("internship"),
            "programming_prereq": f.get("programming_prereq"),
        }),
        "admission": _drop_empty({k: f.get(k) for k in (
            "background_requirement", "gmat_gre_policy", "gmat_gre_note", "toefl_ibt_min", "toefl_ibt_band_min",
            "ielts_min", "ielts_sub_min", "english_waiver", "work_exp_policy", "work_exp_min_years", "cohort_size",
        )}),
        "flexibility": _drop_empty({
            "study_modes": f.get("study_modes"), "intake_months": f.get("intake_months"),
            "delivery": program.get("delivery"), "notes": f.get("notes"),
        }),
        "funding": _drop_empty({"items": [_drop_empty({k: item.get(k) for k in (
            "name", "kind", "amount_kind", "amount", "currency", "percent", "eligible_categories",
            "bond_required", "conditions", "valid_from_year", "valid_to_year",
        )}) for item in program["funding"]]}),
        "deadlines": _drop_empty({"rounds": [_drop_empty({k: r.get(k) for k in (
            "round_no", "round_label", "applicant_category", "opens_on", "closes_on",
        )}) for r in program["deadlines"]]}),
        "location": _drop_empty({
            "university": university["name"], "city": university["city"], "country": university["country_name"],
            "stem_designated": f.get("stem_designated"),
        }),
    }
    return {d: values for d, values in by_dimension.items() if values}


def _sources(program: dict) -> dict[str, tuple[str, ...]]:
    urls: dict[str, list[str]] = {}

    def add(dimension: str, url: str | None) -> None:
        if url and url not in urls.setdefault(dimension, []):
            urls[dimension].append(url)

    for field, sources in program["sources"].items():
        for s in sources:
            if s["role"] == "primary":
                add(FIELD_DIMENSION.get(field, "flexibility"), s["source_url"])
    for fee in program["fees"]:
        add("cost", fee["source_url"])
    for item in program["funding"]:
        add("funding", item["source_url"])
    for r in program["deadlines"]:
        add("deadlines", r["source_url"])
    for area in program["curriculum"]:
        add("curriculum", area.get("source_url"))
    add("location", program["official_url"])
    return {d: tuple(u) for d, u in urls.items()}


def _conflicts(program: dict) -> tuple[Conflict, ...]:
    found = []
    for field, sources in program["sources"].items():
        followed = next((s["source_url"] for s in sources if s["role"] == "primary"), None)
        for s in sources:
            if s["role"] == "conflicting":
                found.append(Conflict(field, FIELD_DIMENSION.get(field, "flexibility"), followed,
                                      s["source_url"], s.get("quote"), s.get("note") or ""))
    return tuple(found)


def build(program: dict) -> ProgramView:
    """`program`: one ComparisonInput programme, as plain data."""
    university = program["university"]
    return ProgramView(
        program_id=program["program_id"], name=program["name"], short_name=program["short_name"],
        university_id=university["university_id"], university=university["name"],
        university_short=university["short_name"], city=university["city"],
        country_code=university["country_code"], country=university["country_name"],
        category=program["category"], is_target=program["is_target"], intake_year=program["intake_year"],
        official_url=program["official_url"], summary=program.get("summary"),
        facts=_facts(program), sources=_sources(program), conflicts=_conflicts(program),
        fees=tuple(program["fees"]), funding=tuple(program["funding"]), deadlines=tuple(program["deadlines"]),
        curriculum=tuple(program["curriculum"]), raw_facts=dict(program["facts"]),
    )
