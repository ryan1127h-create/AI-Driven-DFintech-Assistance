"""
S6 mode "semester_plan" — the courses for one semester: a main plan and
up to two alternatives, each course saying which requirement it counts
toward, unavoidable timetable clashes flagged rather than dropped.

    budget.py   how many units the semester holds
    planner.py  which combination of courses fills it best

The projected degree progress after the plan is added by the workflow,
which owns S3's progress computation.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import CandidatePool, Group, ModeInput, ModeOutput
from app.domains.specialist.course_recommendation.stages.s6_modes import recommendation
from app.domains.specialist.course_recommendation.stages.s6_modes.semester_plan.budget import unit_budget
from app.domains.specialist.course_recommendation.stages.s6_modes.semester_plan.planner import Plan, search


def _clash_cautions(plan: Plan) -> dict[str, str]:
    cautions: dict[str, str] = {}
    for a, b, when in plan.clashes:
        cautions.setdefault(a, f"Clashes with {b} ({when})")
        cautions.setdefault(b, f"Clashes with {a} ({when})")
    return cautions


def _group(plan: Plan, slot_id: str, label: str, pool: CandidatePool, recommended: bool, note: str | None) -> Group:
    cautions = _clash_cautions(plan)
    recommendations = []
    for entry in plan.entries:
        rec = recommendation.build(entry.pick, pool, recommended=recommended, counts_toward=entry.pool.label)
        rec["units"] = entry.units
        clash = cautions.get(entry.code)
        if clash:
            rec["caution"] = f"{rec['caution']} | {clash}" if rec["caution"] else clash
        recommendations.append(rec)
    return {
        "slot_id": slot_id,
        "slot_type": "semester_plan",
        "label": label,
        "required_pick_count": len(plan.entries) if recommended else 0,
        "recommendations": recommendations,
        "note": note,
    }


class SemesterPlan:
    def assemble(self, selected: ModeInput, pool: CandidatePool) -> ModeOutput:
        ctx = selected.plan_context
        budget = unit_budget(ctx.requested_units, ctx.study_mode, ctx.units_remaining)
        best, alternatives, notes = search(selected.plan_pools, budget.units, ctx)

        groups = [_group(best, "plan", f"Plan for {ctx.term.label}", pool, True, None)]
        for index, alt in enumerate(alternatives, start=1):
            swapped_out = sorted(best.codes - alt.codes)
            swapped_in = sorted(alt.codes - best.codes)
            note = f"Swaps {', '.join(swapped_out)} for {', '.join(swapped_in)}."
            groups.append(_group(alt, f"alternative_{index}", f"Alternative {index}", pool, False, note))

        plan = {
            "term": ctx.term.label,
            "study_mode": budget.study_mode,
            "unit_budget": budget.units,
            "budget_source": budget.source,
            "units": best.units,
            "courses": sorted(best.codes),
            "clashes": [{"courses": [a, b], "when": when} for a, b, when in best.clashes],
            "alternatives": [sorted(alt.codes) for alt in alternatives],
        }
        return ModeOutput(groups=groups, plan=plan, notes=budget.notes + notes)
