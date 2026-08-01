"""
Supervisor — intent classification and routing to specialised agents.

Graph flow:
  classify_intent
      ├── "admissions"  →  admissions_node  →  END
      ├── "academic"    →  academic_node    →  END
      ├── "financial"   →  financial_node   →  END
      ├── "assessment"  →  assessment_node  →  END
      └── "general"     →  supervisor_node  →  END
"""

import os
import json
import operator
from typing import TypedDict, Annotated, List
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI  # DeepSeek 走 OpenAI 兼容接口
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage

from app.agents.admissions_agent import admissions_node, assessment_node
from app.agents.academic_agent import academic_node
from app.agents.financial_agent import financial_node

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    # A common.profile.LifecycleStage value, resolved at the chat boundary:
    # prospect | applicant | admitted | current | graduating | alumni
    user_stage: str
    agent_used: str
    reply: str
    intent: str         # admissions | academic | financial | assessment | general


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

Classify the user's latest message into exactly one of five categories:

"admissions" — The user is asking a factual question about: admission \
requirements, eligibility criteria, academic qualifications, GRE / GMAT scores, \
TOEFL / IELTS scores, application steps, application deadlines, application fees, \
or outcome timelines.

"academic" — The user is asking about: specific courses or modules, curriculum \
structure, programme tracks, course descriptions, prerequisites or preclusions, \
the capstone project, course plans (full-time or part-time), graduation \
requirements, unit counts, or semester availability.

"financial" — The user is asking about: tuition fees, acceptance fees, \
scholarships, fee rebates, bond obligations, financial assistance, disbursement \
of funds, or scholarship application procedures.

"assessment" — The user is sharing their own academic background, work \
experience, skills, or profile and asking whether they are suitable or ready \
to apply to the programme. Look for phrases such as "my background is", \
"I have a degree in", "I graduated from", "am I eligible", "should I apply", \
"assess my profile", "what are my chances", or similar self-referential requests.

"general" — The user is doing something that does NOT require looking up \
programme facts: greetings, thank-you messages, follow-up conversational \
questions, questions about the AI assistant itself, or requests for opinions.

"my_documents" — The user is asking what THEY personally still have to submit, \
or whether THEIR OWN application is complete: "what am I still missing", "have I \
submitted everything", "what is left on my application", "is my application \
complete". Choose "admissions" instead when the question is about what the \
programme requires of applicants in general.

"my_courses" — The user is asking what THEY personally should take, given their \
own progress or goals: "what should I take next semester", "which modules fit my \
target role", "plan my remaining courses", "how many units do I have left". \
Choose "academic" instead when the question is about the curriculum in general.

"my_status" — The user is asking where THEIR OWN application currently stands, \
or what happens next for them specifically: "what is the status of my \
application", "where is my application now", "what happens next for me", "has my \
application been reviewed". Choose "admissions" instead for general timelines \
such as "how long does a decision usually take".

"my_comparison" — The user is asking which programme suits THEM, weighing their \
own goals: "which programme is the best fit for me", "should I pick NUS or NTU \
given my background", "which one suits my career goals". Choose "academic" \
instead when the question compares programmes in general, with no reference to \
the user's own situation.

"my_career" — The user is asking which career direction suits THEM: "what career \
should I aim for", "which role fits my skills", "what should I work on to become \
a quant". Choose "academic" instead for general questions about what graduates \
of the programme go on to do.

A note on all five "my_" intents: choose them only when the answer would differ \
from one user to another. If two different users would get the same correct \
answer, it is a general question — use the category that matches its subject.

Respond with ONLY a valid JSON object — no markdown, no explanation:
{"intent": "admissions"}
or
{"intent": "academic"}
or
{"intent": "financial"}
or
{"intent": "assessment"}
or
{"intent": "my_documents"}
or
{"intent": "my_status"}
or
{"intent": "my_comparison"}
or
{"intent": "my_courses"}
or
{"intent": "my_career"}
or
{"intent": "general"}"""


# ── Helpers ────────────────────────────────────────────────────────────────────

# Fallback when the chat surface supplied no stage. Matches app/api/chat.py's own
# default rather than assuming a later stage the user never claimed.
DEFAULT_CHAT_STAGE = "prospect"

# Intents answered by the RAG agents from programme documentation.
_RAG_INTENTS = {"admissions", "academic", "financial", "assessment", "general"}

# Intents answered from the user's own profile by the #4-#7 agents. Kept as a
# separate set so the RAG routes above are unaffected by this addition.
_PERSONALISED_INTENTS = {
    "my_documents", "my_status", "my_comparison", "my_courses", "my_career",
}

_VALID_INTENTS = _RAG_INTENTS | _PERSONALISED_INTENTS


def _build_llm(temperature: float = 0.7) -> ChatOpenAI:
    # 从 Groq 换成 DeepSeek(走 common.config,自动优先 NVIDIA 免费通道、回退 DeepSeek 官方)
    from common import config
    return ChatOpenAI(
        model=config.get_model(),
        api_key=config.get_api_key(),
        base_url=config.get_base_url(),
        temperature=temperature,
        max_tokens=1024,
    )


# ── Nodes ──────────────────────────────────────────────────────────────────────

def classify_intent_node(state: AgentState) -> dict:
    """Classifies the latest user message into one of five intent categories."""
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        return {"intent": "general"}

    llm = _build_llm(temperature=0)
    response = llm.invoke([
        SystemMessage(content=INTENT_CLASSIFIER_PROMPT),
        HumanMessage(content=last_user_message),
    ])

    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "general")
        if intent not in _VALID_INTENTS:
            intent = "general"
    except (json.JSONDecodeError, AttributeError):
        intent = "general"

    print(f"[supervisor] intent classified as: '{intent}'")
    return {"intent": intent}


def _personalised_node(state: AgentState, chat_intent: str, agent_used: str) -> dict:
    """Answer from the user's own profile via the #4-#7 agents.

    Imported lazily so this module still imports in an environment without the
    profile stack, mirroring how the RAG nodes tolerate a missing retriever.
    """
    from app.agents.personal_advice import advise

    reply = advise(chat_intent, state.get("user_stage") or DEFAULT_CHAT_STAGE)
    return {
        "messages": [AIMessage(content=reply)],
        "agent_used": agent_used,
        "reply": reply,
    }


def my_documents_node(state: AgentState) -> dict:
    """#4 — what THIS applicant still has to submit."""
    return _personalised_node(state, "my_documents", "checklist_agent")


def my_status_node(state: AgentState) -> dict:
    """#5 — where THIS application currently stands."""
    return _personalised_node(state, "my_status", "tracker_agent")


def my_comparison_node(state: AgentState) -> dict:
    """#6 — which programme suits THIS user, not which is better in general."""
    return _personalised_node(state, "my_comparison", "comparator_agent")


def my_courses_node(state: AgentState) -> dict:
    """#7 — what THIS student should take next."""
    return _personalised_node(state, "my_courses", "navigator_agent")


def my_career_node(state: AgentState) -> dict:
    """#7 — which direction suits THIS user's skills and goals."""
    return _personalised_node(state, "my_career", "navigator_agent")


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


# ── Routing function ───────────────────────────────────────────────────────────

def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    return intent if intent in _VALID_INTENTS else "general"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_supervisor_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("supervisor",      supervisor_node)
    graph.add_node("admissions",      admissions_node)
    graph.add_node("academic",        academic_node)
    graph.add_node("financial",       financial_node)
    graph.add_node("assessment",      assessment_node)
    graph.add_node("my_documents",    my_documents_node)
    graph.add_node("my_status",       my_status_node)
    graph.add_node("my_comparison",   my_comparison_node)
    graph.add_node("my_courses",      my_courses_node)
    graph.add_node("my_career",       my_career_node)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "admissions":    "admissions",
            "academic":      "academic",
            "financial":     "financial",
            "assessment":    "assessment",
            "my_documents":  "my_documents",
            "my_status":     "my_status",
            "my_comparison": "my_comparison",
            "my_courses":    "my_courses",
            "my_career":     "my_career",
            "general":       "supervisor",
        },
    )

    for _terminal in (
        "admissions", "academic", "financial", "assessment",
        "my_documents", "my_status", "my_comparison", "my_courses", "my_career",
    ):
        graph.add_edge(_terminal, END)
    graph.add_edge("supervisor", END)

    return graph.compile()


# Module-level singleton imported by chat.py
supervisor_graph = build_supervisor_graph()
