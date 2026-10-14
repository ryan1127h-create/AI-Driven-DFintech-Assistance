"""
What a programme comparison asks the student for alongside the answer —
the tool's input_needs, checked by the orchestrator's requirements gate
before the tool runs (see orchestrator/dispatch/requirements.py and
app/tools/input_needs.py).

A comparison never waits for input: the programmes' published facts
answer it on their own. Without the admissions consent it runs
unpersonalised and says so (no consent card — the facts are the point).
With it, two fields that change the answer most are offered under it,
supplementary: the residency category (which fee rate and rebates apply)
and the decision factors (which aspects lead).
"""

from __future__ import annotations

from app.domains.profile.interface import get_profile_for_purpose, missing_purpose_consent
from app.tools.contracts import MissingInputField
from app.tools.input_needs import profile_field_need
from app.tools.turn_context import TurnState

_RESIDENCY_PROMPT = "Are you a Singapore citizen, PR or international applicant? It decides which fees and rebates apply."
_FACTORS_PROMPT = "What matters most to you in choosing a programme?"


def input_needs(state: TurnState) -> tuple[MissingInputField, ...]:
    if not state.user_id or missing_purpose_consent(state.user_id, "adm"):
        return ()
    facts = get_profile_for_purpose(state.user_id, "adm")
    needs = (
        profile_field_need(state, "adm", facts, "residency_category", "supplementary", _RESIDENCY_PROMPT),
        profile_field_need(state, "adm", facts, "decision_factors", "supplementary", _FACTORS_PROMPT),
    )
    return tuple(n for n in needs if n)
