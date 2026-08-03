"""#7 Study-path planner (pure Python, deterministic).

Uses the enriched module_catalog (credits, offered semesters, prereq tree,
workload) to: evaluate prerequisites against the student's completed modules,
track graduation credit progress, and lay recommended modules out across
semesters for a pathway (full-time / part-time) within the sourced per-term
credit bounds.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .engine import _load_catalog, unrecognized_completed

# MSc DFT planning constants.
# Coursework is 40 Units, plus 12 Units Capstone = 52 Units total.  The planner
# surfaces both to avoid mixing application guidance with student audit logic.
COURSEWORK_CREDITS = 40
CAPSTONE_CREDITS = 12
TOTAL_GRAD_CREDITS = COURSEWORK_CREDITS + CAPSTONE_CREDITS

# Per-term credit bounds, sourced from data/dft_knowledge_base.txt
# ("Workload Per Semester": full-time 12-20 Units, part-time 4-12 Units).
_CREDIT_CAP = {"full_time": 20, "part_time": 12}
_CREDIT_MIN = {"full_time": 12, "part_time": 4}
_DEFAULT_CREDIT_CAP = 20
_DEFAULT_CREDIT_MIN = 0
PATHWAYS = ("full_time", "part_time")
# Main teaching terms cycled across years.  Maximum programme duration is 3
# years (data/dft_knowledge_base.txt "Maximum Duration"), i.e. 6 main terms.
_TERM_SEMESTERS = [1, 2]
_MAX_YEARS = 3
_MAX_TERM_SLOTS = _MAX_YEARS * len(_TERM_SEMESTERS)

# data/module_catalog.json currently stores workload_hours as credits * this
# factor, i.e. the field carries no per-module signal of its own.  We detect that
# instead of assuming it, so a future sourced refresh is picked up automatically.
_ESTIMATED_HOURS_PER_CREDIT = 2.5
_HOURS_TOLERANCE = 0.01
_WORKLOAD_UNSOURCED_NOTE = (
    "workload_hours in module_catalog.json is an estimate derived from the credit "
    "count, not sourced per-module NUS contact hours, and the repo carries no "
    "sourced weekly-hours limit to compare it against (data/dft_knowledge_base.txt "
    "bounds the per-semester load in Units only). Per-term hour totals are "
    "indicative only and must not be shown as official workload advice."
)


class PlanInfeasibleError(ValueError):
    """No term layout satisfies the offering / prereq / credit constraints."""


def base_code(token: str) -> str:
    """Strip NUSMods prereq decorations: 'ACC1701%:D' -> 'ACC1701'."""
    return re.split(r"[%:]", token.strip())[0]


def _normalize_code(code: str) -> str:
    """Canonical module-code form used for every catalog lookup."""
    return code.strip().upper()


def _module(code: str, catalog: dict) -> dict:
    """Catalog record for `code`, matched case-insensitively; {} when unknown."""
    return catalog.get(_normalize_code(code), {})


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
    done = {_normalize_code(c) for c in completed}
    out = []
    for code in module_codes:
        tree = _module(code, catalog).get("prereq_tree")
        ok, missing = prereq_satisfied(tree, done)
        out.append(PrereqStatus(code=code, satisfied=ok, missing=missing))
    return out


def _credits(code: str, catalog: dict) -> int | None:
    """Catalog credits for `code`; None when the code is unknown or unpriced.

    Never falls back to a default: an unrecognised code must not contribute
    credits to graduation progress (it would overstate how far along a student is).
    """
    c = _module(code, catalog).get("credits")
    return c if isinstance(c, int) else None


def _sum_credits(codes: list[str], catalog: dict) -> int:
    """Total catalog credits of the *distinct* codes, skipping unpriced ones.

    Deduplicated on the canonical code so a module listed twice (['BMD5301',
    'bmd5301'], or a code repeated in a recommendation set) cannot overstate how
    many credits a student holds or is planning.
    """
    distinct = {_normalize_code(c) for c in codes}
    return sum(mc for mc in (_credits(c, catalog) for c in distinct) if mc is not None)


def graduation_progress(completed: list[str], recommended_codes: list[str],
                        required: int = TOTAL_GRAD_CREDITS) -> dict:
    catalog = _load_catalog()
    done = {_normalize_code(c) for c in completed}
    # Codes we cannot price are excluded from the totals and surfaced instead;
    # unrecognized_completed() is the existing repo-wide notion of "unknown code".
    unknown = unrecognized_completed(completed)
    completed_credits = _sum_credits(completed, catalog)
    planned_credits = _sum_credits(
        [c for c in recommended_codes if _normalize_code(c) not in done], catalog
    )
    remaining = max(0, required - completed_credits - planned_credits)
    return {
        "required": required,
        "coursework_required": COURSEWORK_CREDITS,
        "capstone_required": CAPSTONE_CREDITS,
        "completed_credits": completed_credits,
        "planned_credits": planned_credits,
        "remaining": remaining,
        "unrecognized_completed": unknown,
    }


@dataclass
class TermPlan:
    term: str  # e.g. "Year 1 · Sem 1"
    semester: int
    modules: list[dict] = field(default_factory=list)
    credits: int = 0
    workload_hours: float = 0.0


def _allowed_in(semester: int, offered: list[int] | None) -> bool:
    """Whether `semester` may host a module offered in `offered`.

    `None` (the catalog omits `semesters`, i.e. no availability is sourced) is
    treated as flexible; build_study_plan discloses every such placement in
    `unsourced_offering` so it is never read as sourced guidance.  A sourced
    "offered in no semester" (`[]`) never reaches here -- _reject_unschedulable
    rejects those modules before the layout starts.
    """
    if not offered:
        return True
    return semester in offered


# ---------- prerequisite ordering ----------
def _prereq_pool_codes(tree, completed: set[str],
                       pool: set[str]) -> tuple[bool, set[str]]:
    """(satisfiable from `completed` + `pool`, pool codes needed before the module).

    Same (ok, detail) shape as prereq_satisfied, and for the same reason: the two
    answers are independent.  The flag still signals unsatisfiability upward (an
    `or` / `nOf` must not count an unsatisfiable branch as an alternative), while
    the set keeps the ordering constraints contributed by the branches that CAN be
    met.  Collapsing them either way loses one of the three states: all branches
    satisfiable, some satisfiable, none satisfiable.
    """
    if tree is None:
        return True, set()
    if isinstance(tree, str):
        code = _normalize_code(base_code(tree))
        if code in completed:
            return True, set()
        return code in pool, {code} & pool
    if not isinstance(tree, dict):
        return True, set()
    if "and" in tree:
        return _all_of(tree["and"], completed, pool)
    if "or" in tree:
        return _cheapest_of(tree["or"], completed, pool, 1)
    if "nOf" in tree:
        return _cheapest_of(tree["nOf"][1], completed, pool, tree["nOf"][0])
    return True, set()


def _all_of(children: list, completed: set[str],
            pool: set[str]) -> tuple[bool, set[str]]:
    """Conjunction: satisfiable only if every branch is; ordering from all branches."""
    satisfiable = True
    needed: set[str] = set()
    for child in children:
        ok, sub = _prereq_pool_codes(child, completed, pool)
        satisfiable = satisfiable and ok
        needed |= sub
    return satisfiable, needed


def _cheapest_of(children: list, completed: set[str], pool: set[str],
                 n: int) -> tuple[bool, set[str]]:
    """`n`-of: satisfiable when >= `n` branches are; ordering from the `n` cheapest."""
    subs = [sub for ok, sub in
            (_prereq_pool_codes(c, completed, pool) for c in children) if ok]
    if len(subs) < n:
        return False, set()
    return True, set().union(*sorted(subs, key=len)[:n])


def _blocking_prereqs(code: str, catalog: dict, pool: set[str],
                      completed: set[str]) -> set[str]:
    """Pool codes that must be scheduled in a strictly earlier term than `code`.

    Only the ordering half is used here; whether the tree is satisfiable at all is
    reported to the student by prereq_warnings.  An unmet prerequisite therefore
    neither cancels the ordering of the branches being scheduled nor gets silently
    absorbed into a "satisfied" answer.
    """
    tree = _module(code, catalog).get("prereq_tree")
    _, needed = _prereq_pool_codes(tree, completed, pool)
    return needed - {_normalize_code(code)}


# ---------- term layout ----------
def _schedulable(codes: list[str], catalog: dict) -> tuple[list[str], list[str]]:
    """Split codes into (priced pool, unrecognised), deduped, input order kept."""
    pool: list[str] = []
    unrecognized: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = _normalize_code(raw)
        if code in seen:
            continue
        seen.add(code)
        if _credits(code, catalog) is None:
            unrecognized.append(raw)
        else:
            pool.append(code)
    return pool, unrecognized


def _term_for_slot(slot: int) -> TermPlan:
    year = slot // len(_TERM_SEMESTERS) + 1
    sem = _TERM_SEMESTERS[slot % len(_TERM_SEMESTERS)]
    return TermPlan(term=f"Year {year} · Sem {sem}", semester=sem)


def _term_target(remaining: int, cap: int, min_load: int) -> int:
    """Credits to aim for this term so later terms can still reach `min_load`.

    Plain greedy filling to `cap` leaves a stub final term (e.g. 20 + 4 credits);
    holding back `min_load` for the tail keeps every term at or above the
    per-term minimum whenever the total load allows it.
    """
    if remaining <= cap:
        return remaining
    return max(min_load, min(cap, remaining - min_load))


def _place(tp: TermPlan, code: str, catalog: dict) -> None:
    """Append `code` to `tp` and accumulate its credits / estimated workload."""
    mod = _module(code, catalog)
    mc = _credits(code, catalog) or 0
    tp.modules.append({"code": code, "name": mod.get("name", code), "credits": mc})
    tp.credits += mc
    tp.workload_hours += float(mod.get("workload_hours") or 0.0)


def _fill_term(tp: TermPlan, pending: list[str], placed: set[str], deps: dict,
               catalog: dict, cap: int, target: int) -> None:
    """Place every eligible pending module until the term reaches `target`."""
    for code in list(pending):
        if tp.credits >= target:
            return
        if deps[code] - placed:
            continue  # a prerequisite is still unscheduled
        if not _allowed_in(tp.semester, _module(code, catalog).get("semesters")):
            continue
        if tp.credits + (_credits(code, catalog) or 0) > cap:
            continue
        _place(tp, code, catalog)
        pending.remove(code)


def _lay_out_terms(pool: list[str], deps: dict, catalog: dict, cap: int,
                   min_load: int, pathway: str) -> list[TermPlan]:
    """Assign every pooled module to a term. Raises PlanInfeasibleError on failure."""
    terms: list[TermPlan] = []
    pending = list(pool)
    placed: set[str] = set()  # modules from *earlier* terms only
    for slot in range(_MAX_TERM_SLOTS):
        if not pending:
            break
        tp = _term_for_slot(slot)
        remaining = _sum_credits(pending, catalog)
        _fill_term(tp, pending, placed, deps, catalog, cap,
                   _term_target(remaining, cap, min_load))
        if not tp.modules:
            continue  # nothing can run this slot -> emit no empty term
        terms.append(tp)
        placed.update(m["code"] for m in tp.modules)
    if pending:
        raise PlanInfeasibleError(_infeasible_message(pending, deps, placed,
                                                     catalog, pathway))
    return terms


def _infeasible_message(pending: list[str], deps: dict, placed: set[str],
                        catalog: dict, pathway: str) -> str:
    reasons = []
    for code in pending:
        blockers = sorted(deps[code] - placed)
        if blockers:
            reasons.append(f"{code} still waits on prerequisite(s) {', '.join(blockers)}")
        else:
            offered = _module(code, catalog).get("semesters") or "unknown"
            reasons.append(f"{code} (offered in semester(s) {offered}) never fitted a term")
    return (
        f"{pathway}: cannot schedule {len(pending)} module(s) within the "
        f"{_MAX_TERM_SLOTS}-term ({_MAX_YEARS}-year) maximum programme duration: "
        + "; ".join(reasons)
    )


def _reject_unschedulable(pool: list[str], catalog: dict, cap: int,
                          pathway: str) -> None:
    """Fail fast on modules that no term on this pathway could ever hold."""
    too_big = [c for c in pool if (_credits(c, catalog) or 0) > cap]
    if too_big:
        raise PlanInfeasibleError(
            f"{pathway}: module(s) {', '.join(too_big)} exceed the {cap}-credit "
            f"per-term cap and can never be scheduled on this pathway."
        )
    # `semesters: []` is sourced availability meaning "offered in no semester"
    # (e.g. BMF5358, data/dft_knowledge_base.txt:395-396), unlike an omitted
    # `semesters`, which means the availability is unknown.
    not_offered = [c for c in pool if _module(c, catalog).get("semesters") == []]
    if not_offered:
        raise PlanInfeasibleError(
            f"{pathway}: module(s) {', '.join(not_offered)} are sourced as not "
            f"offered in any semester and can never be scheduled."
        )


def _workload_sourced(catalog: dict) -> bool:
    """True only when some module's workload_hours differs from the credit estimate.

    While every entry equals credits * _ESTIMATED_HOURS_PER_CREDIT the field adds
    no information beyond credits, so any judgement built on it is vacuous.
    """
    for mod in catalog.values():
        hours, credits = mod.get("workload_hours"), mod.get("credits")
        if not isinstance(hours, (int, float)) or not isinstance(credits, int):
            continue
        if abs(hours - credits * _ESTIMATED_HOURS_PER_CREDIT) > _HOURS_TOLERANCE:
            return True
    return False


def build_study_plan(recommended_codes: list[str], pathway: str,
                     completed: list[str] | None = None) -> dict:
    """Lay modules across terms honouring prereq order, offering and credit bounds.

    Guarantees: a module never precedes a prerequisite that is itself being
    scheduled; no empty term is emitted; per-term credits stay within
    [term_credit_min, term_credit_cap] whenever the total load allows it.
    Raises PlanInfeasibleError when the constraints cannot be jointly satisfied.

    No overload verdict is published: the cap above is enforced as a hard
    constraint (so "over cap" cannot occur), and neither per-module contact hours
    nor a weekly-hours limit is sourced in the repo.  `workload_sourced` /
    `workload_note` carry that provenance instead, and `at_credit_cap` reports the
    one sourced heaviness signal the planner really has.
    """
    catalog = _load_catalog()
    cap = _CREDIT_CAP.get(pathway, _DEFAULT_CREDIT_CAP)
    min_load = _CREDIT_MIN.get(pathway, _DEFAULT_CREDIT_MIN)
    done = {_normalize_code(c) for c in completed or []}

    pool, unrecognized = _schedulable(recommended_codes, catalog)
    _reject_unschedulable(pool, catalog, cap, pathway)
    deps = {code: _blocking_prereqs(code, catalog, set(pool), done) for code in pool}
    terms = _lay_out_terms(pool, deps, catalog, cap, min_load, pathway)

    sourced = _workload_sourced(catalog)
    below_min = [tp.term for tp in terms if tp.credits < min_load]
    unsourced_offering = sorted(
        m["code"] for tp in terms for m in tp.modules
        if _module(m["code"], catalog).get("semesters") is None
    )

    return {
        "pathway": pathway,
        "term_credit_cap": cap,
        "term_credit_min": min_load,
        "semesters": [
            # at_credit_cap: the term sits exactly on the sourced per-semester
            # maximum (20 Units full-time / 12 part-time) -- the heaviest legal load.
            {"term": tp.term, "semester": tp.semester, "modules": tp.modules,
             "credits": tp.credits, "workload_hours": tp.workload_hours,
             "at_credit_cap": tp.credits == cap,
             "below_min_credits": tp.credits < min_load}
            for tp in terms
        ],
        "num_terms": len(terms),
        "unrecognized": unrecognized,
        # A short recommendation set can be smaller than one minimum load, so a
        # shortfall is reported rather than raised; the caps are always enforced.
        "min_credits_met": not below_min,
        "below_min_terms": below_min,
        "workload_sourced": sourced,
        "workload_note": None if sourced else _WORKLOAD_UNSOURCED_NOTE,
        # Scheduled modules whose catalog entry omits `semesters` entirely, i.e. the
        # repo sources no availability for them.  They were placed as flexible by
        # _allowed_in, so their term is a scheduling convenience, not NUS guidance.
        "unsourced_offering": unsourced_offering,
    }


def what_if_pathways(recommended_codes: list[str],
                     completed: list[str] | None = None) -> tuple[dict, str | None]:
    """Plan every pathway for comparison -> (feasible plans, joined error or None).

    Each pathway is planned on its own so an infeasibility on one pathway cannot
    discard another pathway's valid plan; the failures are reported instead of
    raised, because a loud explanation beats a silently missing timetable.
    """
    plans: dict[str, dict] = {}
    errors: list[str] = []
    for pathway in PATHWAYS:
        try:
            plans[pathway] = build_study_plan(recommended_codes, pathway, completed)
        except PlanInfeasibleError as exc:
            errors.append(str(exc))
    return plans, "; ".join(errors) or None
