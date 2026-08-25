"""
Comparison Agent — structured, personalised comparison of MSc DFT against
other universities' FinTech-adjacent programmes.

Backed by app.modules.program_comparison.interface.compare_programs(), which
builds a much richer fact table than plain RAG over the 4 competitor_programs
knowledge-base chunks — it also hand-assembles an equivalent NUS-side row
(no such row exists in the knowledge base itself) and computes a transparent,
evidence-backed personal match score per programme (see
app/modules/program_comparison/agents/match_scorer.py). This node's only job
is: resolve the inputs compare_programs() needs (user_id, an optional list of
programme names set by supervisor.py's classify_intent_node — see
agents/state.py — and an optional target_role hint), call it, and reflow its
structured result into one chat reply via
structured_reply.render_structured_reply().

If compare_programs() (or the reflow step) raises for any reason, this falls
back to the original plain-RAG behaviour this node used before the
program_comparison integration (hard-filtered to the 4-chunk "comparison"
topic, see app/services/rag_service.py::_topic_of) — so a bug or outage in
the new integration degrades to a strictly worse but still working answer,
never a 500.

run_comparison() holds the core logic (returns (answer, sources, agent_name)
— agent_name distinguishes the integrated path from the fallback for the
pending intent log, see app/modules/chatbot/service.py::run_turn and
models.py::ConversationState.pending_turn_intents), shared by the
single-intent node below and supervisor.py's dispatch_node multi-intent
fan-out path — same split as run_rag()/make_rag_agent() in agents/rag_agent.py.
"""

from __future__ import annotations

from typing import Callable

from langchain_core.messages import AIMessage

from app.modules.chatbot.agents.rag_agent import make_rag_agent, run_rag
from app.modules.chatbot.agents.state import AgentState, last_human_message
from app.modules.chatbot.agents.structured_reply import render_structured_reply
from app.modules.program_comparison.interface import compare_programs
from app.services.rag_service import cited_sources

_COMPARISON_STYLE_PROMPT = """\
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
that clear if the user asks how authoritative the comparison is.
"""

# Original plain-RAG behaviour, kept as the exception-path fallback.
_legacy_comparison_node = make_rag_agent(
    _COMPARISON_STYLE_PROMPT, "comparison_agent_fallback", filter_topics={"comparison"}
)


def run_comparison(
    state: AgentState, on_event: Callable[[dict], None] | None = None,
) -> tuple[str, list[str], str]:
    """Never raises. Returns (answer, sources, agent_name).

    `on_event`, when given, streams the final answer's tokens as they're
    produced — only pass this when this call's result IS the user-facing
    answer (the single-intent comparison_node below). supervisor.py's
    dispatch_node calls this with on_event left at its default (None) since
    a dispatch branch's draft is only synthesis input, never shown to the
    user verbatim."""
    try:
        result = compare_programs(
            user_id=state["user_id"],
            programs=state.get("program_hints") or None,
            target_role=state.get("target_role_hint"),
        )
        user_message = last_human_message(state["messages"])
        answer, sources = render_structured_reply(
            result, user_message, _COMPARISON_STYLE_PROMPT, on_event=on_event
        )
        return answer, sources, "comparison_agent"
    except Exception as exc:
        print(f"[comparison_agent] Warning: program_comparison integration failed, falling back to RAG — {exc}")
        answer, hits = run_rag(_legacy_comparison_node.spec, state["messages"], on_event=on_event)
        return answer, cited_sources(hits), "comparison_agent_fallback"


def comparison_node(state: AgentState) -> dict:
    on_event = state.get("on_event")
    if on_event is not None:
        on_event({"type": "step", "stage": "answering", "agent": "comparison_agent"})

    answer, sources, agent_name = run_comparison(state, on_event=on_event)

    reply = answer
    if sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

    return {
        "messages": [AIMessage(content=answer)],
        "agent_used": agent_name,
        "reply": reply,
    }
