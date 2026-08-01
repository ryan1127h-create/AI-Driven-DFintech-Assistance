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
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage

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

Respond with ONLY a valid JSON object — no markdown, no explanation:
{"intent": "admissions"}
or
{"intent": "academic"}
or
{"intent": "financial"}
or
{"intent": "assessment"}
or
{"intent": "general"}"""


# ── Helpers ────────────────────────────────────────────────────────────────────

_VALID_INTENTS = {"admissions", "academic", "financial", "assessment", "general"}


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

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "admissions": "admissions",
            "academic":   "academic",
            "financial":  "financial",
            "assessment": "assessment",
            "general":    "supervisor",
        },
    )

    graph.add_edge("admissions", END)
    graph.add_edge("academic",   END)
    graph.add_edge("financial",  END)
    graph.add_edge("assessment", END)
    graph.add_edge("supervisor", END)

    return graph.compile()


# Module-level singleton imported by chat.py
supervisor_graph = build_supervisor_graph()
