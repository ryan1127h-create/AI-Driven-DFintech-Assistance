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
      │       └── "general"     →  supervisor_node   →  END
      └── 2+ intents (from the 6 RAG categories only) →  dispatch_node  →  END
              (runs each matched specialist's retrieval+answer in parallel,
               then merges into one reply — see dispatch_node)

The eight single-intent categories line up with the topic buckets computed in
app/rag/retriever.py::_topic_of (grounded in the knowledge base's actual
source_table/metadata partitions — see plan Phase 3), so each RAG-backed
node's retrieval is scoped to the data it's meant to answer from.
"""

import os
import json
import operator
import concurrent.futures
from typing import TypedDict, Annotated, List
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from app.agents.admissions_agent import admissions_node, assessment_node
from app.agents.academic_agent import academic_node
from app.agents.financial_agent import financial_node
from app.agents.career_agent import career_node
from app.agents.comparison_agent import comparison_node
from app.agents.faq_agent import faq_node
from app.agents.knowledge_agent import run_rag, cited_sources

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_stage: str     # prospect | applicant | admitted | student | alumni
    agent_used: str
    reply: str
    intents: List[str]  # 1-3 of: admissions | academic | financial | career |
                         # comparison | faq | assessment | general


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

Respond with ONLY a valid JSON object — no markdown, no explanation. `intents` is \
always an array, even for a single intent:
{"intents": ["admissions"]}
or
{"intents": ["financial", "admissions"]}
or
{"intents": ["general"]}
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


def _build_llm(temperature: float = 0.7) -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=temperature,
        max_tokens=1024,
    )


# ── Nodes ──────────────────────────────────────────────────────────────────────

def classify_intent_node(state: AgentState) -> dict:
    """Classifies the latest user message into 1-3 intent categories."""
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        return {"intents": ["general"]}

    llm = _build_llm(temperature=0)
    response = llm.invoke([
        SystemMessage(content=INTENT_CLASSIFIER_PROMPT),
        HumanMessage(content=last_user_message),
    ])

    try:
        result = json.loads(response.content.strip())
        raw = result.get("intents", ["general"])
        if isinstance(raw, str):  # tolerate a stray single-string response
            raw = [raw]
        intents = [i for i in raw if i in _VALID_INTENTS][:_MAX_INTENTS] or ["general"]
    except (json.JSONDecodeError, AttributeError, TypeError):
        intents = ["general"]

    print(f"[supervisor] intents classified as: {intents}")
    return {"intents": intents}


def supervisor_node(state: AgentState) -> dict:
    """Handles general conversation that does not require RAG retrieval."""
    llm = _build_llm()
    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + list(state["messages"])
    response = llm.invoke(messages)
    return {
        "messages": [response],
        "agent_used": "supervisor",
        "reply": response.content,
    }


# ── Multi-intent fan-out ───────────────────────────────────────────────────────

# Maps a fan-out-eligible intent name to the RagAgentSpec-carrying node built
# by make_rag_agent() (see app/agents/knowledge_agent.py) — dispatch_node
# reuses each node's .spec directly via run_rag(), rather than duplicating
# the role_prompt/filter_topics/boost_topics definitions here.
_SPECIALIST_NODES = {
    "admissions": admissions_node,
    "academic":   academic_node,
    "financial":  financial_node,
    "career":     career_node,
    "comparison": comparison_node,
    "faq":        faq_node,
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
    Multi-intent fan-out: runs each matched specialist's retrieval+answer in
    parallel (via a thread pool — these are independent blocking calls, and
    running them sequentially would multiply latency by the number of
    intents, defeating the point of "collaborating" agents), then merges the
    partial answers into one reply with a single synthesis LLM call.
    """
    intents = [i for i in state.get("intents", []) if i in _SPECIALIST_NODES]
    if not intents:
        intents = ["faq"]
    specs = [_SPECIALIST_NODES[i].spec for i in intents]

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(specs)) as pool:
        future_to_spec = {pool.submit(run_rag, spec, state["messages"]): spec for spec in specs}
        results = {}
        for future in concurrent.futures.as_completed(future_to_spec):
            spec = future_to_spec[future]
            answer, hits = future.result()
            results[spec.agent_name] = (answer, hits)

    # Keep classification order (not completion order) so the synthesis
    # prompt sees drafts in a predictable, reproducible sequence.
    partials = [(spec.agent_name, *results[spec.agent_name]) for spec in specs]

    drafts = "\n\n".join(
        f"[{name} draft]\n{answer}" for name, answer, _ in partials
    )
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    synthesis_llm = _build_llm(temperature=0.2)
    response = synthesis_llm.invoke([
        SystemMessage(content=_SYNTHESIS_PROMPT.format(drafts=drafts)),
        HumanMessage(content=last_user_message),
    ])

    reply = response.content
    all_hits = [h for _, _, hits in partials for h in hits]
    sources = cited_sources(all_hits)
    if sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)

    agent_used = "+".join(name for name, _, _ in partials)
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
    graph.add_node("supervisor",      supervisor_node)
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


# Module-level singleton imported by chat.py
supervisor_graph = build_supervisor_graph()
