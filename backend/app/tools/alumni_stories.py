"""
Alumni stories under an answer — "alumni with a similar path" — for the
readers the programme wants them for: prospective, applying and admitted
students asking about careers, other programmes or alumni, and enrolled
students asking about careers. Only from alumni who chose to share their
story with that audience (alumni.profiles story_for_applicants /
story_for_students), matched to the reader's goals, and never with contact
details: those stay on Alumni Match, for enrolled students.

Added by the dispatcher after the answer is written (no LLM call), so the
reply's own checked text is untouched; it is localized with the rest.
"""

from __future__ import annotations

from dataclasses import replace

from app.core.logging import get_logger
from app.domains.alumni import interface as alumni
from app.domains.knowledge_retrieval.interface import match_role_tag
from app.domains.profile.interface import get_profile_for_purpose
from app.tools.contracts import ToolAnswer
from app.tools.turn_context import TurnState

logger = get_logger(__name__)

_PRE_ENROLMENT = ("prospect", "rejected", "applicant", "admitted")
_ENROLLED = ("current", "graduating")
_APPLICANT_INTENTS = {"career", "comparison", "alumni"}
_STUDENT_INTENTS = {"career"}
_MAX_BIO = 240

_HEADINGS = {
    "applicants": "Alumni with a similar path (shared by alumni for prospective students):",
    "students": "Alumni with a similar path:",
}
# Enrolled students can contact alumni; prospective ones can't yet.
_CLOSINGS = {
    "students": "You can ask alumni listed on Alumni Match to connect — open it from the sidebar.",
}


def audience(stage: str, intents: list[str]) -> str | None:
    """Whose stories this turn gets, if any."""
    if stage in _PRE_ENROLMENT and _APPLICANT_INTENTS & set(intents):
        return "applicants"
    if stage in _ENROLLED and _STUDENT_INTENTS & set(intents):
        return "students"
    return None


def interests(state: TurnState) -> list[str]:
    """Role tags, most important first: the field asked about this turn,
    then the profile's main and other target roles (consent-filtered)."""
    tags: list[str] = []
    if state.alumni_role_hint:
        tags.append(state.alumni_role_hint)
    if state.target_role_hint:
        tag = match_role_tag(state.target_role_hint)
        if tag:
            tags.append(tag)
    facts = get_profile_for_purpose(state.user_id, "career") if state.user_id else {}
    if facts.get("main_target_role"):
        tags.append(facts["main_target_role"])
    tags.extend(facts.get("target_role_families") or [])
    return list(dict.fromkeys(tags))


def _bio(text: str | None) -> str:
    text = (text or "").strip()
    if len(text) <= _MAX_BIO:
        return text
    cut = text[:_MAX_BIO].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def section(who: str, items: list[dict]) -> str:
    lines = [_HEADINGS[who], ""]
    for story in items:
        year = f", class of {story['class_year']}" if story.get("class_year") else ""
        bio = _bio(story.get("bio"))
        lines.append(f"- **{story['name']}** — {story['position']} at {story['company']}{year}."
                     + (f" {bio}" if bio else ""))
    if who in _CLOSINGS:
        lines += ["", _CLOSINGS[who]]
    return "\n".join(lines)


def with_stories(answer: ToolAnswer, state: TurnState, intents: list[str]) -> ToolAnswer:
    """`answer` with matching alumni stories after it, when the turn's stage
    and intents call for them and someone fits. Never raises: stories are
    extra to the answer."""
    if answer.needs_clarification or answer.agent_used == "orchestrator_error":
        return answer
    who = audience(state.stage, intents)
    if who is None:
        return answer
    try:
        found = alumni.stories(who, interests(state))
    except Exception:
        logger.exception("could not read alumni stories")
        return answer
    if not found:
        return answer
    return replace(answer, text=f"{answer.text.rstrip()}\n\n{section(who, found)}")
