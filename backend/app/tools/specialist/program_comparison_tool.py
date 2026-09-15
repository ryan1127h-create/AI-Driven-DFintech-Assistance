"""
Comparison tool — structured, personalised comparison of MSc DFT against
other universities' FinTech-adjacent programmes.

Backed by program_comparison.interface.compare_programs(), which builds a
much richer fact table than plain RAG over the knowledge base's
competitor_programs chunks — it also hand-assembles an equivalent NUS-side
row and computes a transparent, evidence-backed personal match score per
programme. This tool's own job is only: resolve the inputs
compare_programs() needs from the turn context (user_id, an optional list
of programme names the orchestrator's intent classifier extracted, an
optional target_role hint), call it, and reflow its structured result into
one chat reply via structured_reply.render_structured_reply().

If compare_programs() (or the reflow step) raises for any reason, this
falls back to plain RAG over the knowledge base's "comparison" topic (via
knowledge_qa's generic role-prompt escape hatch) — see
career_planning_tool.py for the identical pattern and rationale.
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa.interface import answer_with_role_prompt
from app.domains.specialist.program_comparison.interface import compare_programs
from app.tools.contracts import OnEvent, Tool, ToolAnswer
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


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    result = compare_programs(
        user_id=state.user_id,
        programs=state.program_hints or None,
        target_role=state.target_role_hint,
    )
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(result, user_message, COMPARISON_STYLE_PROMPT, on_event=on_event)
    return ToolAnswer(text=answer, sources=sources, agent_used="comparison_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    print("[comparison_tool] Warning: program_comparison integration failed, falling back to RAG")
    user_message = last_human_message(state.messages)
    chat_history = to_chat_messages(state.messages)
    answer, sources = answer_with_role_prompt(
        COMPARISON_STYLE_PROMPT, user_message, chat_history,
        filter_topics={"comparison"}, on_event=on_event,
    )
    return ToolAnswer(text=answer, sources=sources, agent_used="comparison_agent_fallback")


COMPARISON_TOOL = Tool(
    name="comparison",
    description="Structured, personalised comparison of MSc DFT against other universities' FinTech programmes.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"comparison"}),
)
