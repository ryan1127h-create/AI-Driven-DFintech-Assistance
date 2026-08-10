"""
RAG agent factory — creates LangGraph node functions backed by the shared
app/services/rag_service.py.

Usage:
    from app.modules.chatbot.agents.rag_agent import make_rag_agent
    my_node = make_rag_agent(role_prompt="...", agent_name="my_agent",
                              boost_topics={"academic"})

Retrieval can optionally be scoped to the topic buckets computed in
app/services/rag_service.py (admissions/academic/financial/career/
comparison/faq — see that module's _topic_of()): filter_topics
hard-restricts candidates (only safe for topics with no overlap elsewhere,
e.g. career/comparison), boost_topics soft-boosts matching hits without
excluding anything else (safer default for topics whose boundaries aren't
clean). Leaving both unset falls back to plain unscoped hybrid retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.clients.kimi_client import build_chat_llm
from app.models.rag import Hit
from app.modules.chatbot.agents.state import AgentState
from app.services.rag_service import build_context, cited_sources, retrieve


@dataclass
class RagAgentSpec:
    role_prompt: str
    agent_name: str
    filter_topics: set[str] | None = None
    boost_topics: set[str] | None = None


_BASE_SYSTEM_PROMPT = """\
{role_prompt}

## Rule 1 — Answer ONLY from the supplied material
- Base your answer exclusively on the REFERENCE MATERIAL provided below. Do not use \
your own prior knowledge about NUS, this programme, or any other university.
- If the material does not contain the answer, say plainly that the information is not \
in the available sources and advise the user to contact the admissions office at \
msc-dft-admissions@nus.edu.sg. Never guess, never infer, never fill gaps with general \
knowledge.
- Reproduce all numbers, dates, amounts, deadlines and course codes exactly as they \
appear in the material. Do not round, convert, recalculate or paraphrase them.

## Rule 2 — Distinguish official policy from advisory guidance
- Material tagged [official] is official programme information. State it directly.
- Material tagged [advisory] is guidance compiled by this project, not official policy. \
You MUST hedge it with wording such as "we suggest", "as a guide", "you may consider", \
and make clear it is a recommendation rather than an official requirement.
- Never present advisory content as an official rule or requirement.

## Rule 3 — When sources disagree
- ⚠️GOVERNS marks the source to follow on that specific point.
- ⚠️SUPERSEDED marks a source overridden only on that specific point — its other \
content, and its own figures, are still valid and should still be given to the user, \
just reframed as reference points rather than hard requirements.
- Never expose this internal tagging to the user — refer to where information comes \
from in plain language (e.g. "the programme FAQ states ...").

## Rule 4 — Style
- Be accurate, concise, and professional.
- Do not write filler like "according to the reference material".

Reference material:
{context}
"""


def run_rag(spec: RagAgentSpec, conversation_messages: list[BaseMessage]) -> tuple[str, list[Hit]]:
    """
    Core single-agent RAG step: retrieve (scoped by spec.filter_topics/
    boost_topics), build a tagged context, call the LLM. Returns the plain
    answer text (no Sources footer — callers append that themselves) and the
    Hits used, so a caller merging several specialists' answers can also
    merge their sources.

    Used both by the node() closures below (single-intent path) and by
    supervisor.py's dispatch_node (multi-intent fan-out path).
    """
    last_user_message = ""
    for msg in reversed(conversation_messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        return "I couldn't identify your question. Could you please rephrase it?", []

    hits = retrieve(last_user_message, top_k=5,
                     filter_topics=spec.filter_topics, boost_topics=spec.boost_topics)
    context = build_context(hits) if hits else (
        "No specific programme information is currently available in the "
        "knowledge base. Please contact the admissions office directly."
    )

    system_prompt = _BASE_SYSTEM_PROMPT.format(role_prompt=spec.role_prompt, context=context)
    messages = [SystemMessage(content=system_prompt)] + list(conversation_messages)
    # max_tokens leaves headroom above the visible answer for Kimi's hidden
    # reasoning budget (see app/clients/kimi_client.py).
    response = build_chat_llm(temperature=0.2, max_tokens=2000).invoke(messages)
    return response.content, hits


def make_rag_agent(
    role_prompt: str, agent_name: str,
    filter_topics: set[str] | None = None, boost_topics: set[str] | None = None,
):
    """
    Returns a LangGraph node function for a RAG-backed agent (single-intent
    path). The node's underlying spec is attached as `node.spec`, so
    supervisor.py's dispatch_node can reuse the same retrieval scoping
    directly via run_rag() for the multi-intent fan-out path.
    """
    spec = RagAgentSpec(role_prompt, agent_name, filter_topics, boost_topics)

    def node(state: AgentState) -> dict:
        answer, hits = run_rag(spec, state["messages"])

        reply = answer
        if hits:
            sources = cited_sources(hits)
            reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

        return {
            "messages": [AIMessage(content=answer)],
            "agent_used": agent_name,
            "reply": reply,
        }

    node.__name__ = agent_name
    node.spec = spec
    return node
