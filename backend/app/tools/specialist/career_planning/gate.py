"""
What career advice asks the student for before (or alongside) answering
— the tool's input_needs, checked by the orchestrator's requirements gate
before the tool runs (see orchestrator/dispatch/requirements.py and
app/tools/input_needs.py).

- Without the consent the career purpose needs, exploration and plans
  ask for it first (they are about the student; without the profile there
  is nothing to go on); a comparison still runs, unpersonalised.
- Plan: the target role is optional — without one the student is shown
  the roles that fit (see s2_assembly/builder.py) and may pick one. The
  job-search timeline, the preferred markets and, for a current student,
  the internship status are supplementary — offered under the plan, never
  holding it up: the timeline has a sound default (right after
  graduating), and asking for it first meant a second card straight
  after the role was picked. A timeline the message states isn't asked.
- Exploration: the functional experience is optional when the profile
  holds no skill evidence at all; the preferred markets are supplementary.
- Compare: nothing is asked. The roles to compare are usually named in
  the message, which the gate can't count (the classifier's role hint
  holds at most one); with fewer than two, the builder falls back to a
  plan or an exploration and says so.

A role named in the message counts as given. The gate runs before the
message is parsed, so it only knows the classifier's role hint.
"""

from __future__ import annotations

from app.domains.profile.interface import get_profile_field, get_profile_for_purpose, missing_purpose_consent
from app.tools.contracts import MissingInputField
from app.tools.input_needs import CONSENT_PROMPT, profile_field_need
from app.tools.turn_context import TurnState, last_human_message

_ROLE_PROMPT = "Which role are you aiming for? I'll plan your readiness for it — or skip to see which roles fit you."
_TIMELINE_PROMPT = "When do you plan to look for work? It sets when your job search falls in the roadmap."
_MARKETS_PROMPT = "Where would you like to work?"
_INTERNSHIP_PROMPT = "Where are you with an internship?"
_FUNCTIONS_PROMPT = "What kind of work have you done so far? It helps match you to roles."

# Profile facts that count as skill evidence (policy/skill_evidence.py's
# fields, plus courses).
_EVIDENCE_FIELDS = (
    "code_level", "ml_ai_level", "data_engineering_level", "blockchain_level", "finance_level",
    "math_stats_level", "tech_stack", "domain_knowledge", "certifications", "prior_coursework",
    "function_experience", "degree_discipline_category", "completed_modules", "current_modules",
)
_JOB_SEARCH_STAGES = frozenset({"admitted", "current", "graduating"})
# Wording that already answers the job-search timing question; the gate
# runs before the message is parsed, so it checks the words itself.
_TIMELINE_WORDS = (
    "after graduat", "upon graduat", "when i graduate", "before graduat", "during the programme",
    "during the program", "while studying", "a year after", "not looking for", "not job",
    "毕业后", "毕业之后", "毕业前", "一毕业", "读书期间", "在读期间", "不找工作", "暂不找",
)


def _states_timeline(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in _TIMELINE_WORDS)


def _has_role(state: TurnState, facts: dict) -> bool:
    return bool(state.target_role_hint or facts.get("main_target_role") or facts.get("target_role_families"))


def input_needs(state: TurnState) -> tuple[MissingInputField, ...]:
    if not state.user_id:
        return ()
    mode = state.career_mode_hint
    consent = missing_purpose_consent(state.user_id, "career")
    if consent:
        if mode == "compare":
            return ()
        return (MissingInputField(slot=f"consent:{consent}", prompt=CONSENT_PROMPT, level="required",
                                  consent_key=consent),)

    facts = get_profile_for_purpose(state.user_id, "career")

    def need(field_key, level, prompt):
        return profile_field_need(state, "career", facts, field_key, level, prompt)

    if mode == "compare":
        return ()
    needs = []
    if mode == "exploration" or not _has_role(state, facts):
        if mode != "exploration":
            needs.append(need("main_target_role", "optional", _ROLE_PROMPT))
        if not any(facts.get(key) not in (None, "", []) for key in _EVIDENCE_FIELDS):
            needs.append(need("function_experience", "optional", _FUNCTIONS_PROMPT))
        needs.append(need("target_markets", "supplementary", _MARKETS_PROMPT))
    else:
        stage = get_profile_field(state.user_id, "lifecycle_stage")
        if stage in _JOB_SEARCH_STAGES and not _states_timeline(last_human_message(state.messages)):
            needs.append(need("job_search_timeline", "supplementary", _TIMELINE_PROMPT))
        needs.append(need("target_markets", "supplementary", _MARKETS_PROMPT))
        if stage == "current":
            needs.append(need("internship_status", "supplementary", _INTERNSHIP_PROMPT))
    return tuple(n for n in needs if n)
