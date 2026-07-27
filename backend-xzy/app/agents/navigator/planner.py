"""#7 Study-path planner (pure Python, deterministic).

Uses the enriched module_catalog (credits, offered semesters, prereq tree,
workload) to: evaluate prerequisites against the student's completed modules,
track graduation credit progress, and lay recommended modules out across
semesters for a pathway (full-time / part-time), with overload warnings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .engine import _load_catalog

# MSc DFT planning constants.
# Coursework is 40 Units, plus 12 Units Capstone = 52 Units total.  The planner
# surfaces both to avoid mixing application guidance with student audit logic.
COURSEWORK_CREDITS = 40
CAPSTONE_CREDITS = 12
TOTAL_GRAD_CREDITS = COURSEWORK_CREDITS + CAPSTONE_CREDITS
_DEFAULT_MC = 4

# Per-term caps by pathway.
_CREDIT_CAP = {"full_time": 20, "part_time": 12}
_CREDIT_MIN = {"full_time": 12, "part_time": 4}
_WORKLOAD_CAP = {"full_time": 50.0, "part_time": 25.0}  # hours/week before overload
# Main teaching terms cycled across years.
_TERM_SEMESTERS = [1, 2]


def base_code(token: str) -> str:
    """Strip NUSMods prereq decorations: 'ACC1701%:D' -> 'ACC1701'."""
    return re.split(r"[%:]", token.strip())[0]


def prereq_satisfied(tree, completed: set[str]) -> tuple[bool, list[str]]:
    """Recursively evaluate a NUSMods prereqTree. Returns (ok, missing_codes)."""
    if tree is None:
        return True, []
    if isinstance(tree, str):
        code = base_code(tree)
        return (code in completed, [] if code in completed else [code])
    if isinstance(tree, dict):
        if "and" in tree:
            missing: list[str] = []
            ok = True
            for child in tree["and"]:
                cok, cmiss = prereq_satisfied(child, completed)
                ok = ok and cok
                missing.extend(cmiss)
            return ok, sorted(set(missing))
        if "or" in tree:
            all_missing: list[str] = []
            for child in tree["or"]:
                cok, cmiss = prereq_satisfied(child, completed)
                if cok:
                    return True, []
                all_missing.extend(cmiss)
            return False, sorted(set(all_missing))  # need one of these
        if "nOf" in tree:
            n, items = tree["nOf"][0], tree["nOf"][1]
            satisfied, missing = 0, []
            for child in items:
                cok, cmiss = prereq_satisfied(child, completed)
                satisfied += 1 if cok else 0
                missing.extend(cmiss)
            return satisfied >= n, sorted(set(missing))
    return True, []


@dataclass
class PrereqStatus:
    code: str
    satisfied: bool
    missing: list[str]


def prereq_warnings(module_codes: list[str], completed: list[str]) -> list[PrereqStatus]:
    catalog = _load_catalog()
    done = {c.strip().upper() for c in completed}
    out = []
    for code in module_codes:
        tree = catalog.get(code, {}).get("prereq_tree")
        ok, missing = prereq_satisfied(tree, done)
        out.append(PrereqStatus(code=code, satisfied=ok, missing=missing))
    return out


def _credits(code: str, catalog: dict) -> int:
    c = catalog.get(code, {}).get("credits")
    return c if isinstance(c, int) else _DEFAULT_MC


def graduation_progress(completed: list[str], recommended_codes: list[str],
                        required: int = TOTAL_GRAD_CREDITS) -> dict:
    catalog = _load_catalog()
    done = {c.strip().upper() for c in completed}
    completed_credits = sum(_credits(c, catalog) for c in completed)
    planned_credits = sum(
        _credits(c, catalog) for c in recommended_codes if c.strip().upper() not in done
    )
    remaining = max(0, required - completed_credits - planned_credits)
    return {
        "required": required,
        "coursework_required": COURSEWORK_CREDITS,
        "capstone_required": CAPSTONE_CREDITS,
        "completed_credits": completed_credits,
        "planned_credits": planned_credits,
        "remaining": remaining,
    }


@dataclass
class TermPlan:
    term: str  # e.g. "Year 1 · Sem 1"
    semester: int
    modules: list[dict] = field(default_factory=list)
    credits: int = 0
    workload_hours: float = 0.0
    overload: bool = False


def _allowed_in(semester: int, offered: list[int]) -> bool:
    if not offered:
        return True  # unknown offering -> flexible
    if offered and all(s in (3, 4) for s in offered):
        return True  # only special terms -> treat as flexible
    return semester in offered


def build_study_plan(recommended_codes: list[str], pathway: str) -> dict:
    """Lay modules across semesters respecting offering + per-term credit cap."""
    catalog = _load_catalog()
    cap = _CREDIT_CAP.get(pathway, 20)
    min_load = _CREDIT_MIN.get(pathway, 0)
    wl_cap = _WORKLOAD_CAP.get(pathway, 50.0)

    terms: list[TermPlan] = []

    def new_term() -> TermPlan:
        idx = len(terms)
        year = idx // len(_TERM_SEMESTERS) + 1
        sem = _TERM_SEMESTERS[idx % len(_TERM_SEMESTERS)]
        tp = TermPlan(term=f"Year {year} · Sem {sem}", semester=sem)
        terms.append(tp)
        return tp

    for code in recommended_codes:
        m = catalog.get(code, {})
        mc = _credits(code, catalog)
        offered = m.get("semesters", [])
        wl = m.get("workload_hours") or 0.0
        placed = False
        for tp in terms:
            if _allowed_in(tp.semester, offered) and tp.credits + mc <= cap:
                tp.modules.append({"code": code, "name": m.get("name", code), "credits": mc})
                tp.credits += mc
                tp.workload_hours += wl
                placed = True
                break
        if not placed:
            tp = new_term()
            # advance term until the module's semester is allowed
            guard = 0
            while not _allowed_in(tp.semester, offered) and guard < 4:
                tp = new_term()
                guard += 1
            tp.modules.append({"code": code, "name": m.get("name", code), "credits": mc})
            tp.credits += mc
            tp.workload_hours += wl

    for tp in terms:
        tp.overload = tp.workload_hours > wl_cap

    return {
        "pathway": pathway,
        "term_credit_cap": cap,
        "term_credit_min": min_load,
        "semesters": [
            {"term": tp.term, "semester": tp.semester, "modules": tp.modules,
             "credits": tp.credits, "workload_hours": tp.workload_hours,
             "overload": tp.overload}
            for tp in terms
        ],
        "num_terms": len(terms),
    }


def what_if_pathways(recommended_codes: list[str]) -> dict:
    """Plan both full-time and part-time for comparison."""
    return {
        "full_time": build_study_plan(recommended_codes, "full_time"),
        "part_time": build_study_plan(recommended_codes, "part_time"),
    }
