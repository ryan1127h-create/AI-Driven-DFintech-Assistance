"""
What a course recommendation asks the student for before (or alongside)
answering — the tool's input_needs, checked by the orchestrator's
requirements gate before the tool runs (see
orchestrator/dispatch/requirements.py and app/tools/input_needs.py).

- The target role is optional: without one the recommendation still runs,
  but can't rank courses by career direction — so the student is asked
  first, and may skip.
- For a semester plan, full- or part-time study is required: it sets the
  semester's unit load (and the message may already say it).
- Vertical interest and Capstone intent are supplementary: they sharpen
  the elective and Capstone advice, and are offered under the answer.

A role named in the message counts as given. Only the profile is read
here (the purpose's consent decides whether anything is asked at all).
"""

from __future__ import annotations

from app.domains.profile.interface import get_profile_for_purpose
from app.tools.contracts import MissingInputField
from app.tools.input_needs import profile_field_need
from app.tools.turn_context import TurnState, last_human_message

_ROLE_PROMPT = (
    "Which role are you aiming for? I'll rank the courses for it — or skip "
    "to see general recommendations."
)
_TRACK_PROMPT = "Which elective Verticals interest you?"
_STUDY_MODE_PROMPT = (
    "Are you studying full-time or part-time? It sets how many units a "
    "semester can hold."
)
# Wording that already answers the study-mode question; the gate runs
# before the message is parsed, so it checks the words itself.
_STUDY_MODE_WORDS = (
    "full-time", "full time", "fulltime", "part-time", "part time", "parttime",
    "全日制", "非全日制", "兼读", "在职读",
)


def _states_study_mode(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in _STUDY_MODE_WORDS)
_CAPSTONE_PROMPT = "Do you plan to do the Capstone, or take electives instead?"


def input_needs(state: TurnState) -> tuple[MissingInputField, ...]:
    if not state.user_id:
        return ()
    facts = get_profile_for_purpose(state.user_id, "course")
    needs = []
    # A semester plan's unit load depends on full- vs part-time study, so
    # it can't be planned without knowing — unless the message says.
    if state.course_mode_hint == "semester_plan" and not _states_study_mode(last_human_message(state.messages)):
        needs.append(profile_field_need(state, "course", facts, "study_mode", "required", _STUDY_MODE_PROMPT))
    has_role = state.target_role_hint or facts.get("main_target_role") or facts.get("target_role_families")
    if not has_role:
        needs.append(profile_field_need(state, "course", facts, "main_target_role", "optional", _ROLE_PROMPT))
    needs.append(profile_field_need(state, "course", facts, "track_interest", "supplementary", _TRACK_PROMPT))
    needs.append(profile_field_need(state, "course", facts, "capstone_intent", "supplementary", _CAPSTONE_PROMPT))
    return tuple(need for need in needs if need)
