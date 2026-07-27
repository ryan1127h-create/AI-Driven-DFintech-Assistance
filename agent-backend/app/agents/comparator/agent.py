"""#6 Comparator Agent entry point.

Produces an objective comparison table plus a goal-tied narrative. Compliance
hard constraints (contract §4 #6):
  - rows come ONLY from the curated dataset
  - the LLM narrative must not produce rankings or "X is better than Y"
  - a disclaimer is always attached
"""
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse
from common.profile import UserProfile

from .engine import compare, violates_ranking

_SYSTEM = (
    "You write a brief, balanced 'fit' summary comparing graduate programmes "
    "for one applicant. STRICT RULES: only use the facts provided; never rank "
    "programmes or say one is better than another; frame everything as fit to "
    "the applicant's stated goals; 2-3 sentences; no new facts."
)


def _narrative(comp, target_roles) -> str:
    role_text = ", ".join(r.value for r in target_roles) if target_roles else "your goals"
    fallback = (
        f"Based on your goals ({role_text}), "
        + (f"{comp.best_for_you} has stronger fit in the relevant dimensions. " if comp.best_for_you
           else "each programme has different strengths, so you should weigh them against your specific goals. ")
        + "The comparison below is for reference only."
    )
    if not llm.available():
        return fallback
    facts = "\n".join(
        f"- {r.program}: "
        + "; ".join(f"{d}={c.text}" for d, c in r.facts.items() if c.kind == "verified")
        + f" (matches your goals on: {', '.join(r.synthesis.matched_roles) or 'none'})"
        for r in comp.rows
    )
    user = (
        f"Applicant goals: {role_text}\n"
        f"Best fit by overlap: {comp.best_for_you or 'n/a'}\n"
        f"Programmes:\n{facts}"
    )
    out = llm.explain(_SYSTEM, user, fallback)
    # Deterministic compliance guard: reject any cross-programme ranking claim.
    return fallback if violates_ranking(out) else out


def _facts_table(comp) -> dict:
    return {
        "rows": [
            {
                "program": r.program,
                "is_target": r.is_target,
                "source_url": r.source_url,
                "fetched_at": r.fetched_at,
                "facts": {
                    d: {"text": c.text, "kind": c.kind,
                        "source_url": c.source_url, "fetched_at": c.fetched_at}
                    for d, c in r.facts.items()
                },
            }
            for r in comp.rows
        ]
    }


def _synthesis(comp, narrative: str) -> dict:
    return {
        "rows": [
            {
                "program": r.program,
                "matched_roles": r.synthesis.matched_roles,
                "role_reasons": r.synthesis.role_reasons,
                "weighted_score": r.synthesis.weighted_score,
                "score_breakdown": r.synthesis.score_breakdown,
            }
            for r in comp.rows
        ],
        "best_for_you": comp.best_for_you,
        "narrative": narrative,
        "weights": comp.weights,
    }


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    priorities = slots.get("priorities")
    comp = compare(profile.target_roles, priorities)

    # consent gate (design doc 13 §5): opt-out -> objective facts only, the
    # entire personalised synthesis zone (scores + best_for_you + narrative) is
    # suppressed.
    personalized = profile.consent_flags.personalization
    if personalized:
        narrative = _narrative(comp, profile.target_roles)
        synthesis = _synthesis(comp, narrative)
        speakable = narrative
    else:
        synthesis = None
        speakable = ("Below is an objective comparison of the programmes (personalisation is disabled). Please weigh the facts against your specific goals; "
                     "the comparison is based on curated public data and is not a ranking.")
    if not profile.target_roles:
        speakable = ("You have not set target roles yet. Below is an objective comparison of the programmes; "
                     "after you set target roles, I can provide more tailored advice.")

    return AgentResponse(
        status="ok",
        answer_type="advisory",  # synthesis, not official policy
        speakable=speakable,
        data={
            "dimensions": comp.dimensions,
            "facts_table": _facts_table(comp),
            "synthesis": synthesis,                 # None when opted out
            "disclaimer": comp.disclaimer,          # always present (compliance)
            "personalized": personalized,
        },
        sources=["programs_dataset"],
    )
