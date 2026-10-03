"""
Comparison tool — structured, personalised comparison of MSc DFT against
other universities' FinTech-adjacent programmes.

Backed by program_comparison.interface.compare_programs(), which builds a
much richer fact table than plain RAG over the knowledge base's
competitor_programs chunks — it also hand-assembles an equivalent NUS-side
row and computes a transparent, evidence-backed personal match score per
programme. program_comparison reads no data itself, so this tool assembles
every input: the knowledge-base chunks its facts table is built from, the
programme names the intent classifier extracted, the target role's skills
(when the message names a known role family), and the applicant facts the
profile allows for the "adm" purpose (GMAT/GRE on file, years of full-time
work experience). It then reflows
the structured result into one chat reply via
structured_reply.render_structured_reply().

If compare_programs() (or the reflow step) raises for any reason, this
falls back to plain RAG over the knowledge base's "comparison" topic (via
knowledge_qa's generic role-prompt escape hatch) — see
career_planning_tool.py for the identical pattern and rationale.
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.interface import get_role_profile, list_chunks, match_role_tag
from app.domains.profile.interface import get_profile_for_purpose
from app.domains.specialist.knowledge_qa.interface import answer_with_role_prompt
from app.domains.specialist.program_comparison.interface import compare_programs
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.knowledge_context import retrieve_context
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages

# The comparison legacy fallback can safely hard-filter because its topic has
# no overlap elsewhere in the corpus.
COMPARISON_STYLE_PROMPT = """\
You are the Programme Comparison Advisor for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your role is to help prospective students compare MSc DFT against other \
universities' FinTech/digital-finance master's programmes, using the \
comparison data and any personal match scores provided.

Hard rules:
- Any personal match score is a transparent, evidence-backed fit signal for \
THIS user (based on their stated skills/profile against each programme's own \
facts) — present it as such, with its reasoning, never as an absolute or \
objective claim that one programme is "better" in general.
- Any information about a competing programme belongs to that university's own \
published sources. Attribute it as such (e.g. "according to [university]'s own \
programme page...") — never present a competitor's information as if it were \
NUS's own, and never present it as independently verified.
- This comparison data (including any match score) is compiled by this project \
for informational purposes, not an official NUS ranking or endorsement. Make \
that clear if the user asks how authoritative the comparison is."""


# total_work_years is stored as a band; the scorer takes whole years, so a
# band counts as its lower bound (never overstating experience).
_WORK_YEARS_LOWER_BOUND = {"0": 0, "<1": 0, "1-3": 1, "3-5": 3, "5-10": 5, "10+": 10}


def _applicant_facts(user_id: str | None) -> dict:
    """What the comparison's match score may use about the user; a None
    value means not known (no consent, or nothing on file)."""
    facts = get_profile_for_purpose(user_id, "adm") if user_id else {}
    tests = facts.get("admission_tests")
    has_gmat_gre = (
        any(isinstance(t, dict) and t.get("key") in ("GRE", "GMAT") for t in tests)
        if tests is not None else (False if facts else None)
    )
    return {
        "has_gmat_gre": has_gmat_gre,
        "work_years": _WORK_YEARS_LOWER_BOUND.get(facts.get("total_work_years")),
    }


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    role_tag = match_role_tag(state.target_role_hint) if state.target_role_hint else None
    role_profile = get_role_profile(role_tag) if role_tag else None
    result = compare_programs(
        list_chunks(),
        programs=state.program_hints or None,
        target_role=state.target_role_hint,
        role_skills=role_profile["required_skills"] if role_profile else [],
        applicant=_applicant_facts(state.user_id),
    )
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(
        result, user_message, COMPARISON_STYLE_PROMPT, on_event=on_event, depth=state.answer_depth,
    )
    return ToolAnswer(text=answer, sources=sources, agent_used="comparison_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    print("[comparison_tool] Warning: program_comparison integration failed, falling back to RAG")
    user_message = last_human_message(state.messages)
    chat_history = to_chat_messages(state.messages)
    retrieved = retrieve_context(user_message, filter_topics={"comparison"}) if user_message else None
    answer = answer_with_role_prompt(
        COMPARISON_STYLE_PROMPT, user_message, chat_history,
        context=retrieved.text if retrieved else None, on_event=on_event, depth=state.answer_depth,
    )
    return ToolAnswer(text=answer, sources=retrieved.sources if retrieved else [], agent_used="comparison_agent_fallback")


COMPARISON_TOOL = Tool(
    name="comparison",
    description="Structured, personalised comparison of MSc DFT against other universities' FinTech programmes.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"comparison"}),
)
