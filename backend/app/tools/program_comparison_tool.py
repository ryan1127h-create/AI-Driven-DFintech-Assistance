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
falls back to plain RAG over the knowledge base's "comparison" topic — see
career_planning_tool.py for the identical pattern and rationale.
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.interface import cited_sources
from app.domains.program_comparison.interface import compare_programs
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.rag_retrieve import COMPARISON_STYLE_PROMPT, LEGACY_COMPARISON_SPEC, run_rag
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message


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
    answer, hits = run_rag(LEGACY_COMPARISON_SPEC, state.messages, on_event=on_event)
    return ToolAnswer(text=answer, sources=cited_sources(hits), agent_used="comparison_agent_fallback")


COMPARISON_TOOL = Tool(
    name="comparison",
    description="Structured, personalised comparison of MSc DFT against other universities' FinTech programmes.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"comparison"}),
)
