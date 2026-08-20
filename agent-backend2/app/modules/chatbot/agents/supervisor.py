"""
Supervisor — intent classification and routing to specialised agents.

Graph flow:
  classify_intent (produces a LIST of 1-3 intents, see below)
      ├── exactly 1 intent
      │       ├── "admissions"  →  admissions_node   →  END
      │       ├── "academic"    →  academic_node     →  END
      │       ├── "financial"   →  financial_node    →  END
      │       ├── "career"      →  career_node       →  END
      │       ├── "comparison"  →  comparison_node   →  END
      │       ├── "faq"         →  faq_node          →  END
      │       ├── "assessment"  →  assessment_node   →  END
      │       └── "general"     →  general_node      →  END
      └── 2+ intents (from the 6 RAG categories only) →  dispatch_node  →  END
              (runs each matched specialist's retrieval+answer in parallel,
               then merges into one reply — see dispatch_node)

Six of the eight single-intent categories (admissions/academic/financial/
career/comparison/faq) line up with the topic buckets computed in
app/services/rag_service.py::_topic_of (grounded in the knowledge base's
actual source_table/metadata partitions), so each RAG-backed node's
retrieval is scoped to the data it's meant to answer from. The remaining
two are exceptions by design: "assessment" runs an unscoped retrieval
across every topic (see specialists/assessment.py), and "general" does no
retrieval at all — neither has a `_topic_of` bucket of its own.
"""

import concurrent.futures
import json
from typing import Callable, List

from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.clients.kimi_client import build_chat_llm
from app.core.config import settings
from app.modules.chatbot.agents.rag_agent import RagAgentSpec, run_rag
from app.modules.chatbot.agents.specialists.academic import academic_node
from app.modules.chatbot.agents.specialists.admissions import admissions_node
from app.modules.chatbot.agents.specialists.assessment import assessment_node
from app.modules.chatbot.agents.specialists.career import career_node, run_career
from app.modules.chatbot.agents.specialists.comparison import comparison_node, run_comparison
from app.modules.chatbot.agents.specialists.faq import faq_node
from app.modules.chatbot.agents.specialists.financial import financial_node
from app.modules.chatbot.agents.state import AgentState, last_human_message
from app.services.rag_service import cited_sources

# ── System prompts ─────────────────────────────────────────────────────────────

SUPERVISOR_SYSTEM_PROMPT = """\
You are an AI assistant for the NUS Master of Science in Digital Financial \
Technology (MSc DFT) programme at the National University of Singapore.

Your role is to support users across the full student lifecycle:
- Prospective students : Help them understand the programme, assess personal \
fit, and explore career outcomes.
- Applicants           : Guide them through application steps, document \
requirements, and deadlines.
- Admitted students    : Support onboarding, initial course planning, and \
pre-arrival milestones.
- Current students     : Academic planning, graduation requirements, and \
career-aligned module recommendations.
- Alumni               : Networking and community engagement opportunities.

Always be professional, warm, and concise. If you are unsure of a specific \
fact, acknowledge it and recommend the user contact the admissions office. \
Ask one clarifying question when the user's intent is unclear."""

INTENT_CLASSIFIER_PROMPT = """\
You are an intent classifier for a university programme assistant chatbot.

Classify the user's latest message into one or more of eight categories. Most \
messages have exactly one intent — only return more than one when the message \
clearly asks about genuinely separate topics (e.g. "what's the application fee \
AND what's the tuition?" is admissions + financial). Return at most 3 intents.

"assessment" and "general" must NEVER appear together with any other intent — \
if either applies, it must be the only element in the list.

The eight categories:

"admissions" — The user is asking a factual question about: admission \
requirements, eligibility criteria, academic qualifications, GRE / GMAT scores, \
TOEFL / IELTS scores, application steps, application deadlines, application fees, \
required documents, or application status / outcome timelines.

"academic" — The user is asking about: specific courses or modules, curriculum \
structure, programme tracks, course descriptions, prerequisites or preclusions, \
the capstone project, course plans (full-time or part-time), graduation \
requirements, unit counts, or semester availability. Use this for questions \
anchored on a course or the curriculum itself.

"financial" — The user is asking about: tuition fees, acceptance fees, \
scholarships, fee rebates, bond obligations, financial assistance, disbursement \
of funds, or scholarship application procedures.

"career" — The user is asking about career paths, job roles, or which skills / \
courses prepare them for a role — e.g. "what should I study to become a quant", \
"what does a compliance career need", "which modules suit a data science role". \
Use this (not "academic") when the question is anchored on a career/role goal \
rather than a specific course.

"comparison" — The user is explicitly comparing this programme against another \
university's programme, e.g. "how does this compare to NTU", "is this better \
than [other programme]", "how is this different from...".

"faq" — The user is asking a general informational question about the \
programme that isn't covered by the categories above — e.g. student life, \
programme overview, general FAQ-style questions.

"assessment" — The user is sharing their own academic background, work \
experience, skills, or profile and asking whether they are suitable or ready \
to apply to the programme. Look for phrases such as "my background is", \
"I have a degree in", "I graduated from", "am I eligible", "should I apply", \
"assess my profile", "what are my chances", or similar self-referential requests.

"general" — The user is doing something that does NOT require looking up \
programme facts at all: greetings, thank-you messages, follow-up conversational \
questions, questions about the AI assistant itself, or requests for opinions.

Additionally, extract two more OPTIONAL signals from the user's LATEST message \
only (used to personalise the "career" and "comparison" answers — leave them \
out/null/empty whenever nothing is actually said, never guess):

"target_role_hint" — if the user names or describes a specific job/career goal \
they're aiming for (e.g. "quant researcher", "compliance officer", "product \
manager", "I want to work in blockchain"), put that phrase here verbatim. \
Otherwise null.

"program_hints" — if the user explicitly names one or more OTHER universities \
or programmes they want compared against (e.g. "NTU", "SMU", "HKUST"), list \
each name here exactly as given. Otherwise an empty list.

Respond with ONLY a valid JSON object — no markdown, no explanation. `intents` is \
always an array, even for a single intent; `target_role_hint` and `program_hints` \
are always present (null / [] when nothing was mentioned):
{"intents": ["admissions"], "target_role_hint": null, "program_hints": []}
or
{"intents": ["financial", "admissions"], "target_role_hint": null, "program_hints": []}
or
{"intents": ["career"], "target_role_hint": "quant researcher", "program_hints": []}
or
{"intents": ["comparison"], "target_role_hint": null, "program_hints": ["NTU"]}
or
{"intents": ["general"], "target_role_hint": null, "program_hints": []}
(etc. — any 1-3 of: admissions, academic, financial, career, comparison, faq, \
assessment, general)"""


# ── Helpers ────────────────────────────────────────────────────────────────────

_VALID_INTENTS = {
    "admissions", "academic", "financial", "career", "comparison",
    "faq", "assessment", "general",
}

# Intents that can be fanned out to in parallel when 2+ are detected together.
# assessment/general are deliberately excluded — see prompt above.
_FANOUT_INTENTS = {"admissions", "academic", "financial", "career", "comparison", "faq"}

_MAX_INTENTS = 3


# ── Nodes ──────────────────────────────────────────────────────────────────────

def classify_intent_node(state: AgentState) -> dict:
    """Classifies the latest user message into 1-3 intent categories, plus
    two optional personalisation hints (target_role_hint, program_hints) —
    see agents/state.py and the module docstrings of
    agents/specialists/career.py / comparison.py for how those are used."""
    last_user_message = last_human_message(state["messages"])

    if not last_user_message:
        return {"intents": ["general"], "target_role_hint": None, "program_hints": []}

    # max_tokens leaves headroom above the still-small JSON output (a couple
    # more short fields than before) for Kimi's hidden reasoning budget (see
    # app/clients/kimi_client.py).
    #
    # The whole call (LLM invoke + parsing) is inside one try/except: a
    # failed LLM call (rate limit, network error, API error — this node had
    # no protection against that at all before, unlike every other LLM call
    # site in this codebase: rag_service.retrieve(), conversation_service.
    # summarize_block(), structured_reply.render_structured_reply(),
    # specialists/career.py::run_career(), specialists/comparison.py::
    # run_comparison()) is treated the same as a malformed/unparseable
    # response — both fall back to "general" (routes to general_node, a
    # plain conversational reply) rather than crashing the whole turn.
    try:
        llm = build_chat_llm(temperature=0, max_tokens=1500)
        response = llm.invoke([
            SystemMessage(content=INTENT_CLASSIFIER_PROMPT),
            HumanMessage(content=last_user_message),
        ])

        result = json.loads(response.content.strip())
        raw = result.get("intents", ["general"])
        if isinstance(raw, str):  # tolerate a stray single-string response
            raw = [raw]
        intents = [i for i in raw if i in _VALID_INTENTS][:_MAX_INTENTS] or ["general"]

        target_role_hint = result.get("target_role_hint")
        if not isinstance(target_role_hint, str) or not target_role_hint.strip():
            target_role_hint = None
        else:
            target_role_hint = target_role_hint.strip()

        raw_programs = result.get("program_hints", [])
        if not isinstance(raw_programs, list):
            raw_programs = []
        program_hints = [p.strip() for p in raw_programs if isinstance(p, str) and p.strip()]
    except Exception as exc:
        print(f"[supervisor] Warning: intent classification failed, defaulting to 'general' — {exc}")
        intents, target_role_hint, program_hints = ["general"], None, []

    print(f"[supervisor] intents classified as: {intents}")
    return {"intents": intents, "target_role_hint": target_role_hint, "program_hints": program_hints}


def general_node(state: AgentState) -> dict:
    """Handles general conversation that does not require RAG retrieval."""
    llm = build_chat_llm(temperature=0.7, max_tokens=2000)
    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + list(state["messages"])
    response = llm.invoke(messages)
    return {
        "messages": [response],
        "agent_used": "supervisor",
        "reply": response.content,
    }


# ── Multi-intent fan-out ───────────────────────────────────────────────────────

# Uniform fan-out contract: every fan-out-eligible intent maps to a callable
# (state) -> (answer, sources, agent_name) — `career`/`comparison` plug in
# their run_career()/run_comparison() directly (they already integrate with
# career_planning/program_comparison, with their own RAG fallback baked in —
# see agents/specialists/career.py, comparison.py), the four unchanged
# plain-RAG specialists get a thin adapter around run_rag()/cited_sources()
# so their result shape matches. This replaces the old `.spec`-attribute
# convention (make_rag_agent nodes carried a RagAgentSpec dispatch_node read
# directly) — career/comparison no longer have a single fixed spec, so the
# fan-out mechanism can't depend on one.
def _rag_handler(spec: RagAgentSpec) -> Callable[[AgentState], tuple]:
    def handler(state: AgentState) -> tuple[str, list, str]:
        answer, hits = run_rag(spec, state["messages"])
        return answer, cited_sources(hits), spec.agent_name
    return handler


_FANOUT_HANDLERS: dict[str, Callable[[AgentState], tuple]] = {
    "admissions": _rag_handler(admissions_node.spec),
    "academic":   _rag_handler(academic_node.spec),
    "financial":  _rag_handler(financial_node.spec),
    "faq":        _rag_handler(faq_node.spec),
    "career":     run_career,
    "comparison": run_comparison,
}

_SYNTHESIS_PROMPT = """\
The user's message touched on multiple topics. Below are draft answers from \
different specialist advisors, each covering one part of the question.

Combine them into a single, coherent reply that:
- Answers every part of the user's original question.
- Does not repeat the same information in multiple places.
- Reads naturally, not like a list of disconnected fragments stitched together.
- Preserves every fact, figure, date, and hedging/advisory wording EXACTLY as \
given in the drafts below — do not invent, drop, soften, or "correct" anything.
- Replies in the same language the user's question was asked in.

Do not mention that this answer was assembled from multiple drafts or advisors. \
The drafts below may contain internal citation markers such as "SOURCE 1", \
"[official]", "[advisory]", "⚠️GOVERNS", or "⚠️SUPERSEDED" — these are for your \
reference only. Never reproduce them in your reply; rephrase whatever they were \
attached to in plain language instead (e.g. "the programme FAQ states ..." \
rather than "according to SOURCE 1 [advisory]").

{drafts}
"""


def dispatch_node(state: AgentState) -> dict:
    """
    Multi-intent fan-out: runs each matched intent's handler in parallel (via
    a thread pool — these are independent blocking calls, and running them
    sequentially would multiply latency by the number of intents, defeating
    the point of "collaborating" agents), then merges the partial answers
    into one reply with a single synthesis LLM call.

    career/comparison handlers can now each trigger several sequential LLM
    calls internally (career_planning/program_comparison integration — see
    agents/specialists/career.py, comparison.py), so this fan-out is capped
    by settings.dispatch_branch_timeout_seconds: whichever branches haven't
    settled by then are treated as "not ready" rather than blocking the
    whole reply indefinitely. The executor is deliberately NOT used as a
    context manager (`with ThreadPoolExecutor(...) as pool:` would call
    shutdown(wait=True) on exit and silently re-introduce the same
    unbounded wait) — shutdown(wait=False) lets any still-running branch
    finish on its own time without holding up this function's return.
    """
    intents = [i for i in state.get("intents", []) if i in _FANOUT_HANDLERS]
    if not intents:
        intents = ["faq"]
    handlers = [(intent, _FANOUT_HANDLERS[intent]) for intent in intents]

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(handlers))
    future_to_intent = {pool.submit(handler, state): intent for intent, handler in handlers}
    done, not_done = concurrent.futures.wait(
        future_to_intent, timeout=settings.dispatch_branch_timeout_seconds
    )

    results: dict[str, tuple[str, list, str]] = {}
    for future in done:
        intent = future_to_intent[future]
        try:
            results[intent] = future.result()
        except Exception as exc:
            print(f"[supervisor] Warning: dispatch branch '{intent}' failed — {exc}")
            results[intent] = (
                "(no answer available for this part of the question)", [], f"{intent}_error",
            )
    for future in not_done:
        intent = future_to_intent[future]
        print(f"[supervisor] Warning: dispatch branch '{intent}' did not finish within "
              f"{settings.dispatch_branch_timeout_seconds}s")
        results[intent] = (
            "(this part of the answer wasn't ready in time — please ask again if you still need it)",
            [], f"{intent}_timeout",
        )
    pool.shutdown(wait=False)

    # Keep classification order (not completion order) so the synthesis
    # prompt sees drafts in a predictable, reproducible sequence.
    partials = [(intent, *results[intent]) for intent in intents]

    drafts = "\n\n".join(
        f"[{name} draft]\n{answer}" for _, answer, _, name in partials
    )
    last_user_message = last_human_message(state["messages"])

    synthesis_llm = build_chat_llm(temperature=0.2, max_tokens=2000)
    response = synthesis_llm.invoke([
        SystemMessage(content=_SYNTHESIS_PROMPT.format(drafts=drafts)),
        HumanMessage(content=last_user_message),
    ])

    reply = response.content
    # Sources from the new modules are already list[str] (not RAG Hit
    # objects), so — unlike before — merging is a plain order-preserving
    # dedupe rather than a call through cited_sources().
    seen: set[str] = set()
    sources: list[str] = []
    for _, _, branch_sources, _ in partials:
        for s in branch_sources:
            if s not in seen:
                seen.add(s)
                sources.append(s)
    if sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

    agent_used = "+".join(name for _, _, _, name in partials)
    return {
        "messages": [AIMessage(content=reply)],
        "agent_used": agent_used,
        "reply": reply,
    }


# ── Routing function ───────────────────────────────────────────────────────────

def route_by_intents(state: AgentState) -> str:
    intents = [i for i in state.get("intents", []) if i in _VALID_INTENTS]
    if not intents:
        return "general"
    if len(intents) == 1:
        return intents[0]

    fanout = [i for i in intents if i in _FANOUT_INTENTS]
    if len(fanout) >= 2:
        return "dispatch"
    return fanout[0] if fanout else "general"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_supervisor_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("supervisor",      general_node)
    graph.add_node("admissions",      admissions_node)
    graph.add_node("academic",        academic_node)
    graph.add_node("financial",       financial_node)
    graph.add_node("career",          career_node)
    graph.add_node("comparison",      comparison_node)
    graph.add_node("faq",             faq_node)
    graph.add_node("assessment",      assessment_node)
    graph.add_node("dispatch",        dispatch_node)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intents,
        {
            "admissions": "admissions",
            "academic":   "academic",
            "financial":  "financial",
            "career":     "career",
            "comparison": "comparison",
            "faq":        "faq",
            "assessment": "assessment",
            "general":    "supervisor",
            "dispatch":   "dispatch",
        },
    )

    graph.add_edge("admissions", END)
    graph.add_edge("academic",   END)
    graph.add_edge("financial",  END)
    graph.add_edge("career",     END)
    graph.add_edge("comparison", END)
    graph.add_edge("faq",        END)
    graph.add_edge("assessment", END)
    graph.add_edge("supervisor", END)
    graph.add_edge("dispatch",   END)

    return graph.compile()


# Module-level singleton imported by app/modules/chatbot/service.py
supervisor_graph = build_supervisor_graph()
