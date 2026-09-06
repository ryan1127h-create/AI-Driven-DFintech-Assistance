"""
Routing — classifies the latest user message into 1-3 of nine intent
categories, plus a small set of optional personalisation/localisation
signals, then either answers directly (no tool matched — plain
conversation), declines (out of scope), or hands off to dispatch.py for
the one- or many-tool path.

Six of the nine categories line up with a registered Tool's
trigger_intents (see tools/registration.py) — "assessment", "general" and
"off_topic" are the three exceptions, each of which must appear alone,
never combined with another intent: assessment is its own registered tool
but is never fanned out alongside others (see FANOUT_INTENTS below);
"general" has no tool at all — it's the plain-conversation fallback this
module answers directly, with no retrieval; "off_topic" also has no tool —
dispatch.py answers it with a fixed decline, no LLM call at all, since this
assistant exists only to support NUS MSc DFT students and applicants (see
the module docstring's rationale in dispatch.py::_route).

This same call also detects reply_language — the language the final reply
should end up in (see orchestrator/localization.py, which acts on it as
the very last step of a turn, after every tool/business-logic prompt below
has generated its answer in English as usual). Detecting it here, in the
one call that already reads the latest message, costs nothing extra;
piggybacking it onto every generation prompt instead would not only cost
more, it would be less reliable — a prompt already carrying this many
domain rules can easily bury one more instruction (see
orchestrator/localization.py's docstring for why the two concerns are kept
apart like this).
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
Ask one clarifying question when the user's intent is unclear.

This assistant exists specifically to support NUS MSc DFT students and \
applicants. If a message is entirely unrelated to the programme or the \
user's own application/study journey, politely decline and redirect the \
user back to what you can help with instead of attempting it."""

INTENT_CLASSIFIER_PROMPT = """\
You are an intent classifier for a university programme assistant chatbot. \
This chatbot exists ONLY to help prospective students, applicants, and \
current students of the NUS MSc Digital Financial Technology (DFT) \
programme — nothing else is in scope.

Classify the user's latest message into one or more of nine categories. Most \
messages have exactly one intent — only return more than one when the message \
clearly asks about genuinely separate topics (e.g. "what's the application fee \
AND what's the tuition?" is admissions + financial). Return at most 3 intents.

"assessment", "general", and "off_topic" must NEVER appear together with any \
other intent — if any of the three applies, it must be the only element in \
the list.

The nine categories:

"admissions" — The user is asking a factual question about: admission \
requirements, eligibility criteria, academic qualifications, GRE / GMAT scores, \
TOEFL / IELTS scores, application steps, application deadlines, application fees, \
required documents, or application status / outcome timelines.

"academic" — The user is asking about: specific courses or modules, curriculum \
structure, programme tracks, course descriptions, prerequisites or preclusions, \
the capstone project, course plans (full-time or part-time), graduation \
requirements, unit counts, or semester availability. Use this for questions \
anchored on what to study or which programme modules to choose, even when the \
user mentions a career goal.

"financial" — The user is asking about: tuition fees, acceptance fees, \
scholarships, fee rebates, bond obligations, financial assistance, disbursement \
of funds, or scholarship application procedures.

"career" — The user is asking about career paths, job roles, role readiness, \
capability evidence, portfolios, networking, interviews, or job-search milestones \
— e.g. "what does a compliance career need", "am I ready for a quant role", or \
"how should I prepare for product-manager interviews". Do NOT use this category \
for requests about courses, modules, curricula, or what to study; those are academic.

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
programme facts at all, but is still within this assistant's purpose: \
greetings, thank-you messages, follow-up conversational questions, questions \
about the AI assistant itself, or requests for opinions about the programme \
or the user's own plans.

"off_topic" — The message has NOTHING to do with the DFT programme or the \
user's own application/study journey — general knowledge questions, requests \
to write unrelated content (code, essays, poems, etc.), questions about other \
products/companies/topics, or anything else this assistant has no business \
answering. Only use this when the ENTIRE message is unrelated — if any part \
of it is genuinely about the DFT programme, classify that part normally \
instead and ignore the unrelated fragment.

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

Also detect "reply_language" — the single language the FINAL reply should be \
written in, as a lowercase ISO 639-1 code (e.g. "en", "zh", "ja", "ko", "fr"):

- Identify the MATRIX language of the user's latest message — the language \
carrying its grammatical structure — not just any language that appears in it. \
A message mostly in one language with an embedded English term, proper noun, \
or course code (e.g. "请问 tuition fee 大概多少") still has that one matrix \
language; ignore the embedded term.
- Never produce a reply in more than one language, even if the message itself \
mixes languages roughly evenly — pick the language of the actual \
question/request, not a greeting or filler phrase, as the tie-breaker.
- If you genuinely cannot tell (no clear matrix language, or too little text \
to judge), use "en" — the one language guaranteed to be understood here.

Respond with ONLY a valid JSON object — no markdown, no explanation. `intents` is \
always an array, even for a single intent; `target_role_hint` and `program_hints` \
are always present (null / [] when nothing was mentioned); `reply_language` is \
always present:
{"intents": ["admissions"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
or
{"intents": ["financial", "admissions"], "target_role_hint": null, "program_hints": [], "reply_language": "zh"}
or
{"intents": ["career"], "target_role_hint": "quant researcher", "program_hints": [], "reply_language": "en"}
or
{"intents": ["comparison"], "target_role_hint": null, "program_hints": ["NTU"], "reply_language": "ja"}
or
{"intents": ["general"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
or
{"intents": ["off_topic"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
(etc. — any 1-3 of: admissions, academic, financial, career, comparison, faq, \
assessment, general, off_topic)"""

VALID_INTENTS = {
    "admissions", "academic", "financial", "career", "comparison",
    "faq", "assessment", "general", "off_topic",
}

# Intents that can be fanned out to in parallel when 2+ are detected
# together. assessment/general/off_topic are deliberately excluded — see
# prompt above.
FANOUT_INTENTS = {"admissions", "academic", "financial", "career", "comparison", "faq"}

_MAX_INTENTS = 3


_DEFAULT_REPLY_LANGUAGE = "en"


def classify_intent(
    messages: list, on_event: OnEvent | None = None,
) -> tuple[list[str], str | None, list[str], str]:
    """Classifies the latest user message into 1-3 intent categories, plus
    two optional personalisation hints (target_role_hint, program_hints)
    and reply_language (see orchestrator/localization.py). Returns
    (intents, target_role_hint, program_hints, reply_language) —
    (["general"], None, [], "en") on an empty message or any classification
    failure — "en" is the correct failure default here regardless of what
    language the conversation has been in: a broken classification call is
    exactly the situation where guessing wrong is more likely than usual,
    and English is the one language guaranteed to be understood."""
    last_user_message = last_human_message(messages)
    if not last_user_message:
        return ["general"], None, [], _DEFAULT_REPLY_LANGUAGE

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

        reply_language = result.get("reply_language")
        if not isinstance(reply_language, str) or not reply_language.strip():
            reply_language = _DEFAULT_REPLY_LANGUAGE
        else:
            reply_language = reply_language.strip().lower()
    except Exception as exc:
        print(f"[routing] Warning: intent classification failed, defaulting to 'general' — {exc}")
        intents, target_role_hint, program_hints = ["general"], None, []
        reply_language = _DEFAULT_REPLY_LANGUAGE

    print(f"[routing] intents classified as: {intents} (reply_language={reply_language})")
    if on_event is not None:
        on_event({
            "type": "step", "stage": "classified", "intents": intents,
            "target_role_hint": target_role_hint, "program_hints": program_hints,
            "reply_language": reply_language,
        })
    return intents, target_role_hint, program_hints, reply_language


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
