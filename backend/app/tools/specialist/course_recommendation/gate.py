"""
What a course recommendation asks the student for before (or alongside)
answering — the tool's input_needs, checked by the orchestrator's
requirements gate before the tool runs (see
orchestrator/dispatch/requirements.py and app/tools/input_needs.py).

- The target role is optional: without one the recommendation still runs,
  but can't rank courses by career direction — so the student is asked
  first, and may skip.
- Vertical interest and Capstone intent are supplementary: they sharpen
  the elective and Capstone advice, and are offered under the answer.

A role named in the message counts as given. Only the profile is read
here (the purpose's consent decides whether anything is asked at all).
"""

from __future__ import annotations

from app.domains.profile.interface import get_profile_for_purpose
from app.tools.contracts import MissingInputField
from app.tools.input_needs import profile_field_need
from app.tools.turn_context import TurnState

_ROLE_PROMPT = (
    "Which role are you aiming for? I'll rank the courses for it — or skip "
    "to see general recommendations."
)
_TRACK_PROMPT = "Which elective Verticals interest you?"
_CAPSTONE_PROMPT = "Do you plan to do the Capstone, or take electives instead?"


def input_needs(state: TurnState) -> tuple[MissingInputField, ...]:
    if not state.user_id:
        return ()
    facts = get_profile_for_purpose(state.user_id, "course")
    needs = []
    has_role = state.target_role_hint or facts.get("main_target_role") or facts.get("target_role_families")
    if not has_role:
        needs.append(profile_field_need(state, "course", facts, "main_target_role", "optional", _ROLE_PROMPT))
    needs.append(profile_field_need(state, "course", facts, "track_interest", "supplementary", _TRACK_PROMPT))
    needs.append(profile_field_need(state, "course", facts, "capstone_intent", "supplementary", _CAPSTONE_PROMPT))
    return tuple(need for need in needs if need)
