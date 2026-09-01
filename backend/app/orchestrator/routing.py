"""
Routing — classifies the latest user message into 1-3 of eight intent
categories, plus two optional personalisation hints, then either answers
directly (no tool matched — plain conversation) or hands off to
dispatch.py for the one- or many-tool path.

Six of the eight categories line up with a registered Tool's
trigger_intents (see tools/registration.py) — "assessment" and "general"
are the two exceptions: assessment is its own registered tool but is
never fanned out alongside others (see _FANOUT_INTENTS below), and
"general" has no tool at all — it's the plain-conversation fallback
this module answers directly, with no retrieval.
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from app.adapters.deepseek_adapter import llm
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.turn_context import last_human_message, to_chat_messages

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

VALID_INTENTS = {
    "admissions", "academic", "financial", "career", "comparison",
    "faq", "assessment", "general",
}

# Intents that can be fanned out to in parallel when 2+ are detected
# together. assessment/general are deliberately excluded — see prompt above.
FANOUT_INTENTS = {"admissions", "academic", "financial", "career", "comparison", "faq"}

_MAX_INTENTS = 3


def classify_intent(messages: list, on_event: OnEvent | None = None) -> tuple[list[str], str | None, list[str]]:
    """Classifies the latest user message into 1-3 intent categories, plus
    two optional personalisation hints (target_role_hint, program_hints).
    Returns (intents, target_role_hint, program_hints) — ["general"] with
    no hints on an empty message or any classification failure."""
    last_user_message = last_human_message(messages)
    if not last_user_message:
        return ["general"], None, []

    if on_event is not None:
        on_event({"type": "step", "stage": "classifying"})

    # The whole call (LLM invoke + parsing) is inside one try/except: a
    # failed LLM call (rate limit, network error, API error) is treated the
    # same as a malformed/unparseable response — both fall back to
    # "general" (a plain conversational reply) rather than failing the
    # whole turn.
    try:
        response = llm.complete(INTENT_CLASSIFIER_PROMPT, last_user_message, temperature=0, max_tokens=1500)
        result = json.loads(response.strip())
        raw = result.get("intents", ["general"])
        if isinstance(raw, str):  # tolerate a stray single-string response
            raw = [raw]
        intents = [i for i in raw if i in VALID_INTENTS][:_MAX_INTENTS] or ["general"]

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
        print(f"[routing] Warning: intent classification failed, defaulting to 'general' — {exc}")
        intents, target_role_hint, program_hints = ["general"], None, []

    print(f"[routing] intents classified as: {intents}")
    if on_event is not None:
        on_event({
            "type": "step", "stage": "classified", "intents": intents,
            "target_role_hint": target_role_hint, "program_hints": program_hints,
        })
    return intents, target_role_hint, program_hints


def run_general_chat(messages: list, on_event: OnEvent | None = None) -> ToolAnswer:
    """Plain conversational reply — no retrieval, no tool. The orchestrator's
    own built-in answer for whatever no registered tool covers."""
    if on_event is not None:
        on_event({"type": "step", "stage": "answering", "agent": "supervisor"})

    chunks: list[str] = []
    for chunk in llm.stream(SUPERVISOR_SYSTEM_PROMPT, to_chat_messages(messages), temperature=0.7, max_tokens=2000):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})

    return ToolAnswer(text="".join(chunks), agent_used="supervisor")


def reply_message(answer: ToolAnswer) -> AIMessage:
    """The AIMessage form of a tool's answer, appended to conversation
    history — text only, no Sources footer (that's a display-layer
    concern, added to ToolAnswer.text by dispatch.py before it reaches the
    caller, never persisted as if the model said it)."""
    return AIMessage(content=answer.text)
