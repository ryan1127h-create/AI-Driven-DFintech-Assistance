"""
The derived-label rules, as pure functions of data the service has already
read: no I/O, no LLM, every result explainable from its inputs. Thresholds
are named constants so a rule change is one edit here plus a new
RULES_VERSION.
"""

from __future__ import annotations

import re
from datetime import date

RULES_VERSION = "2026-10"

# Dictionary stage codes per lifecycle stage.
STAGE_CODES = {
    "prospect": "PRO", "applicant": "APP", "admitted": "ADM",
    "current": "CUR", "graduating": "GRD", "alumni": "ALU",
}

# --- profile_usability --------------------------------------------------------

# Share of the stage's P1 fields filled for a "rich" profile.
RICH_P1_SHARE = 0.6
# Never asked of the user, so never required of them.
_NOT_USER_FIELDS = {"lifecycle_stage", "user_id"}
# Stages whose questionnaire doesn't ask for the motivation.
_NO_MOTIVATION_STAGES = {"GRD", "ALU"}


def _filled(value) -> bool:
    return value not in (None, "", [], {})


def _user_answerable(definition: dict) -> bool:
    """Fields the user (or their CV) can supply; DB-only ones come from
    school records whenever they exist and are never held against a
    profile."""
    sources = set(definition.get("sources") or [])
    return (
        definition["field_key"] not in _NOT_USER_FIELDS
        and definition.get("user_visible")
        and definition.get("storage") in ("value", "sis")
        and bool(sources & {"QA", "CV"})
    )


def _effective_tier(definition: dict, values: dict) -> str:
    """The dictionary tier with its tier_condition applied."""
    key, tier = definition["field_key"], definition["tier"]
    if key == "main_target_role":
        return tier if len(values.get("target_role_families") or []) > 1 else "P1"
    if key == "target_role_families":
        return tier if values.get("career_goal_clarity") != "exploring" else "P1"
    if key == "weekly_study_hours" and values.get("study_mode") == "part_time":
        return "P0"
    return tier


def profile_usability(values: dict, definitions: dict, stage_code: str | None) -> str:
    """rich: every P0 field and most P1 fields filled; usable: every P0
    field filled and the motivation known; otherwise not_ready."""
    applicable = [
        d for d in definitions.values()
        if _user_answerable(d) and stage_code in (d.get("stages") or [])
    ]
    p0 = [d for d in applicable if _effective_tier(d, values) == "P0"]
    p1 = [d for d in applicable if _effective_tier(d, values) == "P1"]
    if any(not _filled(values.get(d["field_key"])) for d in p0):
        return "not_ready"
    if stage_code not in _NO_MOTIVATION_STAGES and motivation_segment(values) is None:
        return "not_ready"
    p1_share = sum(_filled(values.get(d["field_key"])) for d in p1) / len(p1) if p1 else 1.0
    return "rich" if p1_share >= RICH_P1_SHARE else "usable"


# --- motivation_segment ---------------------------------------------------------

def motivation_segment(values: dict) -> str | None:
    """The stated reason for the master's; without one, only two cautious
    inferences (no full-time work as a student -> launch, still exploring
    careers -> explore), otherwise unknown."""
    stated = values.get("program_motivation")
    if stated:
        return stated
    if values.get("total_work_years") in ("0", "<1") and values.get("employment_status") == "student":
        return "launch"
    if values.get("career_goal_clarity") == "exploring":
        return "explore"
    return None


# --- readiness_gap ------------------------------------------------------------------

# Level each area expects (the programme's Python requirement is level 2,
# "has written data-processing scripts independently").
REQUIRED_LEVELS = {"programming": 2, "maths_stats": 2, "finance": 1}
_LEVEL_FIELDS = {"programming": "code_level", "maths_stats": "math_stats_level", "finance": "finance_level"}
# Degree disciplines and prior coursework that point to readiness in an area.
_EVIDENCE = {
    "programming": ({"cs_se", "information_systems"}, {"programming", "dsa", "databases", "machine_learning"}),
    "maths_stats": ({"math_stats_physics"}, {"probability_statistics", "linear_algebra", "econometrics", "stochastic_calculus"}),
    "finance": ({"finance_econ_accounting"}, {"corporate_finance", "investments_derivatives", "accounting"}),
}
READINESS_STAGES = {"PRO", "APP", "ADM", "CUR"}


def readiness_gap(values: dict) -> dict:
    """Per area {level, required, gap, evidence, status}. The self-rating
    decides when given (met / gap); without one, background evidence makes
    it likely_met, and no evidence leaves it unknown, never a gap."""
    discipline = values.get("degree_discipline_category")
    coursework = set(values.get("prior_coursework") or [])
    result = {}
    for area, required in REQUIRED_LEVELS.items():
        level = values.get(_LEVEL_FIELDS[area])
        disciplines, courses = _EVIDENCE[area]
        evidence = ([f"degree: {discipline}"] if discipline in disciplines else []) + [
            f"coursework: {c}" for c in sorted(coursework & courses)
        ]
        if isinstance(level, int):
            gap = max(0, required - level)
            status = "met" if gap == 0 else "gap"
        else:
            gap = None
            status = "likely_met" if evidence else "unknown"
        result[area] = {"level": level, "required": required, "gap": gap, "evidence": evidence, "status": status}
    return result


# --- drop_off_risk --------------------------------------------------------------------

STALE_DOCS_DAYS = 14
STALE_DRAFT_DAYS = 30
_WORRYING_CONCERNS = {"cost", "visa", "eligibility"}


def _days_since(when, today: date) -> int | None:
    if when is None:
        return None
    return (today - (when.date() if hasattr(when, "date") else when)).days


def drop_off_risk(application: dict | None, required_items: set[str], values: dict, today: date) -> str | None:
    """For an applicant's bound application: high when it has stalled
    (documents required and still missing for over STALE_DOCS_DAYS, or a
    draft untouched for over STALE_DRAFT_DAYS); mid on a warning sign
    (required documents missing, several other programmes in view, or a
    cost/visa/eligibility concern); otherwise low. None without one."""
    if application is None:
        return None
    status = application.get("status")
    history = application.get("status_history") or []
    last_change = history[-1]["changed_at"] if history else (application.get("updated_at") or application.get("submission_date"))
    since_change = _days_since(last_change, today)
    missing_required = [
        d["item_key"] for d in application.get("documents") or []
        if not d.get("submitted") and d["item_key"] in required_items
    ]
    if status == "DOCS_REQUIRED" and missing_required and (since_change or 0) > STALE_DOCS_DAYS:
        return "high"
    if status == "DRAFT" and (since_change or 0) > STALE_DRAFT_DAYS:
        return "high"
    concerns = {c.get("key") if isinstance(c, dict) else c for c in values.get("concerns") or []}
    if missing_required or len(values.get("competing_programs") or []) >= 2 or concerns & _WORRYING_CONCERNS:
        return "mid"
    return "low"


# --- graduation_risk_flags --------------------------------------------------------------

# Units in progress this semester above which the load counts as heavy.
MAX_CURRENT_UNITS = {"full_time": 24, "part_time": 12}
# A low weekly study time combined with more units than this is a risk too.
LOW_HOURS_UNIT_LIMIT = 12
CAPSTONE_CODE = "FT5007"
MAX_LEVEL_4000_ELECTIVES = 2  # rule:cur_elective_rules
_TERM_RE = re.compile(r"^AY(\d{4})/\d{2} Sem([12])$")


def semester_index(term: str | None) -> int | None:
    """AY2027/28 Sem1 -> 2027*2, Sem2 -> 2027*2+1; None for anything else."""
    match = _TERM_RE.match(term or "")
    return int(match.group(1)) * 2 + int(match.group(2)) - 1 if match else None


def current_semester_index(today: date) -> int:
    """Aug-Dec is semester 1 of AY y/y+1, Jan-Jul semester 2 of AY y-1/y."""
    if today.month >= 8:
        return today.year * 2
    return (today.year - 1) * 2 + 1


def graduation_risk_flags(
    values: dict,
    *,
    completed_progress: dict,
    projected_progress: dict,
    planned_progress: dict,
    current_units: float,
    current_codes: set[str],
    planned_codes: set[str],
    today: date,
) -> list[dict]:
    """[{code, message}] for a current or graduating student. Progress
    dicts are course_recommendation's degree progress over completed
    courses, completed + current, and completed + current + planned."""
    flags = []

    def flag(code: str, message: str) -> None:
        flags.append({"code": code, "message": message})

    standing = values.get("academic_standing")
    if values.get("gpa_current_band") == "<3.0" or (standing and standing != "good"):
        flag("gpa_below_requirement", "GPA is below the 3.0 needed to graduate, or academic standing is not good.")

    expected = semester_index(values.get("expected_grad_term"))
    if expected is not None and expected - current_semester_index(today) <= 1 and projected_progress["core_mandatory_remaining"]:
        flag("core_behind", "Mandatory core courses still outstanding with at most one semester left: "
             + ", ".join(projected_progress["core_mandatory_remaining"]) + ".")

    if planned_progress["elective_level4000_used"] > MAX_LEVEL_4000_ELECTIVES:
        flag("level4000_over_limit", "More than two 4000-level electives taken or planned; the extra ones won't count.")

    if CAPSTONE_CODE in (current_codes | planned_codes) and completed_progress["core_mandatory_remaining"]:
        flag("capstone_prerequisites", "Capstone project taken or planned before the mandatory core courses are completed.")

    limit = MAX_CURRENT_UNITS.get(values.get("study_mode"), MAX_CURRENT_UNITS["full_time"])
    if current_units > limit or (values.get("weekly_study_hours") == "<10" and current_units > LOW_HOURS_UNIT_LIMIT):
        flag("overload", f"{current_units:g} units this semester is a heavy load for the time available.")
    return flags
