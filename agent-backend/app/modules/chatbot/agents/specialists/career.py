"""
Career Agent — personalised career-fit assessment, skill-gap analysis, and
course recommendations for a target role.

Backed by app.modules.career_planning.interface.create_career_plan(), which
itself reuses app.modules.course_recommendation (role -> skills -> eligible
courses -> LLM pick) plus a RAG pass over the "career" topic for narrative
context — see those modules for the actual logic. This node's only job is:
resolve the two inputs those modules need (user_id, and an optional
target_role hint set by supervisor.py's classify_intent_node — see
agents/state.py), call create_career_plan(), and reflow its structured
result into one chat reply via structured_reply.render_structured_reply().

If create_career_plan() (or the reflow step) raises for any reason, this
falls back to the original plain-RAG behaviour this node used before the
career_planning integration (hard-filtered to the 6-chunk "career" topic, see
app/services/rag_service.py::_topic_of) — so a bug or outage in the new
integration degrades to a strictly worse but still working answer, never a
500.

run_career() holds the core logic (returns (answer, sources, agent_name) —
agent_name distinguishes the integrated path from the fallback for the
persisted turn log, see repository.py::log_turn), shared by the single-intent
node below and supervisor.py's dispatch_node multi-intent fan-out path — same
split as run_rag()/make_rag_agent() in agents/rag_agent.py.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.modules.career_planning.interface import create_career_plan
from app.modules.chatbot.agents.rag_agent import make_rag_agent, run_rag
from app.modules.chatbot.agents.state import AgentState, last_human_message
from app.modules.chatbot.agents.structured_reply import render_structured_reply
from app.services.rag_service import cited_sources

_CAREER_STYLE_PROMPT = """\
You are the Career Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers career pathways relevant to MSc DFT graduates (e.g. \
Financial Data Science / AI, Compliance / RegTech, and other FinTech-adjacent \
roles), the skills each pathway typically requires, and which programme \
courses build toward a given pathway.

Important: this career-pathway mapping and any course recommendations are \
guidance compiled by this project — NOT an official NUS career placement \
guarantee or official curriculum requirement. Always frame it as suggestion \
("this pathway typically calls for...", "students aiming for this role often \
take..."), never as a rule the student must follow, and never promise \
employment outcomes."""

# Original plain-RAG behaviour, kept as the exception-path fallback.
_legacy_career_node = make_rag_agent(_CAREER_STYLE_PROMPT, "career_agent_fallback", filter_topics={"career"})


def run_career(state: AgentState) -> tuple[str, list[str], str]:
    """Never raises. Returns (answer, sources, agent_name)."""
    try:
        result = create_career_plan(user_id=state["user_id"], target_role=state.get("target_role_hint"))
        user_message = last_human_message(state["messages"])
        answer, sources = render_structured_reply(result, user_message, _CAREER_STYLE_PROMPT)
        return answer, sources, "career_agent"
    except Exception as exc:
        print(f"[career_agent] Warning: career_planning integration failed, falling back to RAG — {exc}")
        answer, hits = run_rag(_legacy_career_node.spec, state["messages"])
        return answer, cited_sources(hits), "career_agent_fallback"


def career_node(state: AgentState) -> dict:
    answer, sources, agent_name = run_career(state)

    reply = answer
    if sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

    return {
        "messages": [AIMessage(content=answer)],
        "agent_used": agent_name,
        "reply": reply,
    }
