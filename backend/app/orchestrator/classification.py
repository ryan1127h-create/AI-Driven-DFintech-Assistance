"""
Classification — classifies the latest user message into 1-3 of ten intent
categories, plus a small set of optional personalisation/localisation
signals, then either answers directly (no tool matched — plain
conversation), declines (out of scope), or hands off to dispatch.py for
the one- or many-tool path.

Eight of the ten categories line up with a registered Tool's
trigger_intents (see tools/registration.py), and any of them may come
together — up to three tools then answer in parallel and their replies are
joined (dispatch/execution.py). The two without a tool must appear alone:
"general" is the plain-conversation fallback this module answers directly
(run_general_chat(), grounded in the programme's current facts); "off_topic"
gets a fixed decline from dispatch/__init__.py with no LLM call at all,
since this assistant exists only to support NUS MSc DFT students and
applicants (see dispatch/routing.py::route).

This same call also detects reply_language — the language the reply is
written in. Detecting it here, in the one call that already reads the
latest message, costs nothing extra. turn_service resolves it (falling back
to the user's preference), the generation steps write in it (see
app/core/reply_language.py), and dispatch/localization.py converts only a
finished reply found in another language.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from app.adapters.deepseek_adapter import llm
from app.core import answer_depth, reply_language
from app.core.logging import get_logger
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.programme_facts import current_facts
from app.tools.turn_context import PreviousTurn, last_human_message, to_chat_messages

logger = get_logger(__name__)

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

Always be professional, warm, and concise. Ask one clarifying question when \
the user's intent is unclear.

Programme facts (fees, dates, requirements, durations, funding, course \
content) come ONLY from the CURRENT PROGRAMME FACTS below — never from your \
own memory of NUS or this programme. For anything they don't cover, say you \
don't have that detail here and invite the user to ask about it directly \
(e.g. "what courses are in the programme?"), so the right specialist can \
look it up.

This assistant exists specifically to support NUS MSc DFT students and \
applicants. If a message is entirely unrelated to the programme or the \
user's own application/study journey, politely decline and redirect the \
user back to what you can help with instead of attempting it."""

INTENT_CLASSIFIER_PROMPT = """\
You are an intent classifier for a university programme assistant chatbot. \
This chatbot exists ONLY to help prospective students, applicants, and \
current students of the NUS MSc Digital Financial Technology (DFT) \
programme — nothing else is in scope.

Classify the user's latest message into one or more of ten categories. Most \
messages have exactly one intent — only return more than one when the message \
clearly asks about genuinely separate topics (e.g. "what's the application fee \
AND what's the tuition?" is admissions + financial). Return at most 3 intents.

"general" and "off_topic" must NEVER appear together with any other intent — \
if either applies, it must be the only element in the list. The others may be \
combined, e.g. "which electives should I take for AI, and what's the tuition?" \
is course_recommendation + financial.

The input may start with a PREVIOUS TURN section: the last exchange in this \
conversation, for context only. Classify ONLY the LATEST MESSAGE, but read it \
in that light: a short message that answers what the assistant just asked or \
offered — picking one of the options it listed, naming a role, course or \
value, "yes", "no", "the second one" — continues the previous turn's topic, so \
give it the previous turn's intent and fill the hints from what it picks (e.g. \
the assistant listed roles to choose from and the latest message is "software \
engineering": intents ["career"], target_role_hint "software engineering", \
career_mode_hint "plan"; the assistant listed programmes to compare and the \
latest message is "HKU and the second one": intents ["comparison"], \
program_hints with the programmes picked, comparison_mode_hint "compare"). A message that is complete on its own or clearly \
changes the subject is classified on its own, ignoring the previous turn. \
reply_language always comes from the LATEST MESSAGE alone.

The ten categories:

"admissions" — The user is asking a factual question about: admission \
requirements, eligibility criteria, academic qualifications, GRE / GMAT scores, \
TOEFL / IELTS scores, application steps, application deadlines, application fees, \
required documents, or application status / outcome timelines.

"academic" — The user is asking about: specific courses or modules, curriculum \
structure, programme tracks, course descriptions, prerequisites or preclusions, \
the capstone project, course plans (full-time or part-time), graduation \
requirements, unit counts, or semester availability, as a general/informational \
question — NOT a request for a personalised pick. Use this for "what courses \
exist", "what's the capstone about", "what are the elective tracks" — anything \
answerable the same way for any student.

"course_recommendation" — The user wants a PERSONALISED recommendation of which \
specific courses/electives THEY should take, based on their own background, \
completed courses, or career goals — e.g. "which electives should I take", \
"recommend courses for a career in AI", "what should I take next semester", \
"help me plan my course selection". The distinguishing signal vs. "academic" is \
personalisation: the user wants courses picked FOR THEM, not general information \
about what courses exist.

"financial" — The user is asking about: tuition fees, acceptance fees, \
scholarships, fee rebates, bond obligations, financial assistance, disbursement \
of funds, or scholarship application procedures.

"career" — The user is asking about career paths, job roles, role readiness, \
capability evidence, portfolios, networking, interviews, or job-search milestones \
— e.g. "what does a compliance career need", "am I ready for a quant role", \
"which jobs suit my background", "data analyst or data engineer?", or \
"how should I prepare for product-manager interviews". Do NOT use this category \
for requests about courses, modules, curricula, or what to study; those are academic.

"comparison" — The user is (a) comparing MSc DFT with another master's \
programme — at another university or another NUS programme — e.g. "how does \
this compare to NTU", "DFT or HKUST?", "how is this different from the MSBA"; \
(b) asking about ANOTHER programme's own facts — its fees, deadlines, entry \
requirements, length or curriculum — e.g. "what are NTU MSc FinTech's fees?", \
"when does HKUST's application close?"; or (c) asking which other programmes \
exist or meet some conditions, e.g. "any part-time FinTech master's in Hong \
Kong?". A question about MSc DFT's own facts alone is admissions, financial \
or academic, never comparison.

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
only (used to personalise the "career", "comparison", and \
"course_recommendation" answers — leave them out/null/empty whenever nothing \
is actually said, never guess):

"target_role_hint" — if the user names or describes a specific job/career goal \
they're aiming for (e.g. "quant researcher", "compliance officer", "product \
manager", "I want to work in blockchain"), put that phrase here verbatim. \
Otherwise null.

"program_hints" — if the user names one or more OTHER universities or \
programmes (to compare against, or to ask about), e.g. "NTU", "SMU", "HKUST", \
"港科大", list each name here exactly as given. Otherwise an empty list.

"course_mode_hint" — ONLY when the intents include "course_recommendation", \
which kind of course advice the user wants; otherwise null:
- "ad_hoc": courses matching something specific they describe (a topic, \
skill, style or workload), e.g. "recommend practical Python courses", "any \
electives on blockchain?";
- "semester_plan": a plan for a particular semester or term, often with a \
unit load, e.g. "plan my courses for next semester, 12 units";
- "degree_overview": general advice on what to take for the degree, e.g. \
"which electives should I take?", "help me plan my course selection".

"comparison_mode_hint" — ONLY when the intents include "comparison", which \
kind of answer the user wants; otherwise null:
- "compare": MSc DFT weighed against one or more named programmes, or how \
they differ, e.g. "DFT vs NTU on fees", "how is this different from HKUST?";
- "detail": the facts of one other programme only, e.g. "what are SMU MQF's \
fees?", "南洋理工的金融科技什么时候截止申请？";
- "explore": which programmes exist or meet some conditions, without naming \
them, e.g. "any part-time FinTech programmes in Hong Kong?", "what other \
programmes are like this one?".

"career_mode_hint" — ONLY when the intents include "career", which kind of \
career advice the user wants; otherwise null:
- "exploration": which roles would suit them, with no role chosen yet, e.g. \
"what jobs fit my background?", "what could I do after this programme?";
- "compare": weighing two or more roles against each other, e.g. "data \
analyst or data engineer — which suits me?";
- "plan": getting ready for one role, e.g. "am I ready for a quant role?", \
"how should I prepare to become a risk analyst?".

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
to judge, e.g. "ok", a course code or a number), use null — the user's saved \
language preference decides then.

Respond with ONLY a valid JSON object — no markdown, no explanation. `intents` is \
always an array, even for a single intent; `target_role_hint` and `program_hints` \
are always present (null / [] when nothing was mentioned); `reply_language` is \
always present (null when you can't tell); `course_mode_hint` is always present \
(null unless the intents include course_recommendation), and so are \
`career_mode_hint` (null unless the intents include career) and \
`comparison_mode_hint` (null unless the intents include comparison):
{"intents": ["admissions"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
or
{"intents": ["financial", "admissions"], "target_role_hint": null, "program_hints": [], "reply_language": "zh"}
or
{"intents": ["career"], "target_role_hint": "quant researcher", "program_hints": [], "reply_language": "en", "career_mode_hint": "plan"}
or
{"intents": ["comparison"], "target_role_hint": null, "program_hints": ["NTU"], "reply_language": "ja", "comparison_mode_hint": "compare"}
or
{"intents": ["comparison"], "target_role_hint": null, "program_hints": ["港科大"], "reply_language": "zh", "comparison_mode_hint": "detail"}
or
{"intents": ["course_recommendation"], "target_role_hint": "compliance officer", "program_hints": [], "reply_language": "en", "course_mode_hint": "degree_overview"}
or
{"intents": ["course_recommendation"], "target_role_hint": null, "program_hints": [], "reply_language": "zh", "course_mode_hint": "ad_hoc"}
or
{"intents": ["general"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
or
{"intents": ["off_topic"], "target_role_hint": null, "program_hints": [], "reply_language": "en"}
(etc. — any 1-3 of: admissions, academic, financial, career, comparison, faq, \
assessment, course_recommendation, general, off_topic)"""

VALID_INTENTS = {
    "admissions", "academic", "financial", "career", "comparison",
    "faq", "assessment", "course_recommendation", "general", "off_topic",
}

_MAX_INTENTS = 3

# The kinds of course advice course_mode_hint distinguishes (see the prompt).
COURSE_MODES = {"degree_overview", "ad_hoc", "semester_plan"}
# The kinds of career advice career_mode_hint distinguishes.
CAREER_MODES = {"exploration", "plan", "compare"}
# The kinds of programme comparison comparison_mode_hint distinguishes.
COMPARISON_MODES = {"compare", "detail", "explore"}


@dataclass(frozen=True)
class Classification:
    """What one classifier call read from the latest message: its intents,
    and the hints the matching tools use (None / empty when not said)."""

    intents: list[str]
    target_role_hint: str | None = None
    program_hints: list[str] = field(default_factory=list)
    # None when the message's language can't be told.
    reply_language: str | None = None
    course_mode_hint: str | None = None
    career_mode_hint: str | None = None
    comparison_mode_hint: str | None = None


def _classifier_input(message: str, previous_turn: PreviousTurn | None) -> str:
    """The latest message alone, or — after an earlier turn — preceded by
    that turn: what the user said, how the reply ended, which tool
    answered, and any question it was waiting on."""
    if previous_turn is None:
        return message
    lines = [
        "PREVIOUS TURN (context only — do not classify it):",
        f"User: {previous_turn.user_message[:300]}",
        f"Assistant (ending of its reply): {previous_turn.reply_tail()}",
    ]
    if previous_turn.intents:
        lines.append(f"It was classified as: {', '.join(previous_turn.intents)}")
    for context in previous_turn.contexts:
        mode = f", mode {context['mode']}" if context.get("mode") else ""
        lines.append(f"Answered by: {context.get('tool')}{mode}")
    awaiting = previous_turn.awaiting
    if awaiting and awaiting.get("kind") == "choose_role":
        options = "; ".join(f"{o['label']} ({o['key']})" for o in awaiting.get("options", []))
        lines.append(f"The assistant asked the user to choose one of these roles: {options}")
    elif awaiting and awaiting.get("kind") == "choose_programs":
        options = "; ".join(f"{o['label']} ({o['key']})" for o in awaiting.get("options", []))
        lines.append(f"The assistant asked the user to choose programmes to compare with MSc DFT from: {options}")
    elif awaiting and awaiting.get("kind") == "fields":
        lines.append(f"The assistant asked the user for: {', '.join(awaiting.get('field_keys', []))}")
    elif awaiting and awaiting.get("kind") == "consent":
        lines.append("The assistant asked the user to turn on a consent.")
    lines += ["", "LATEST MESSAGE (classify this):", message]
    return "\n".join(lines)


def _text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _mode(result: dict, key: str, intent: str, intents: list[str], modes: set[str]) -> str | None:
    value = result.get(key)
    return value if intent in intents and value in modes else None


def _parse(response: str) -> Classification:
    result = json.loads(response.strip())
    raw = result.get("intents", ["general"])
    if isinstance(raw, str):  # tolerate a stray single-string response
        raw = [raw]
    intents = [i for i in raw if i in VALID_INTENTS][:_MAX_INTENTS] or ["general"]
    programs = result.get("program_hints", [])
    language = _text(result.get("reply_language"))
    return Classification(
        intents=intents,
        target_role_hint=_text(result.get("target_role_hint")),
        program_hints=[p.strip() for p in programs if isinstance(p, str) and p.strip()]
        if isinstance(programs, list) else [],
        reply_language=language.lower() if language else None,
        course_mode_hint=_mode(result, "course_mode_hint", "course_recommendation", intents, COURSE_MODES),
        career_mode_hint=_mode(result, "career_mode_hint", "career", intents, CAREER_MODES),
        comparison_mode_hint=_mode(result, "comparison_mode_hint", "comparison", intents, COMPARISON_MODES),
    )


def classify_intent(
    messages: list, on_event: OnEvent | None = None, previous_turn: PreviousTurn | None = None,
) -> Classification:
    """Classifies the latest user message into 1-3 intent categories, plus
    the hints the matching tools use: target_role_hint and program_hints,
    and a mode hint for course recommendation, career advice and programme
    comparison; also reply_language (see orchestrator/dispatch/
    localization.py). Just ["general"] on an empty message or any
    classification failure. `previous_turn`, when given, is shown to the
    model as context for reading a short follow-up (see
    _classifier_input()). reply_language is None whenever the message's
    language can't be told; turn_service then falls back to the user's
    language preference, and to English without one."""
    last_user_message = last_human_message(messages)
    if not last_user_message:
        return Classification(intents=["general"])

    if on_event is not None:
        on_event({"type": "step", "stage": "classifying"})

    # A failed LLM call (rate limit, network, API error) and an unparseable
    # answer are treated alike: a plain conversational reply rather than a
    # failed turn.
    try:
        response = llm.complete(
            INTENT_CLASSIFIER_PROMPT, _classifier_input(last_user_message, previous_turn),
            temperature=0, max_tokens=1500,
        )
        classified = _parse(response)
    except Exception:
        logger.exception("intent classification failed, defaulting to 'general'")
        classified = Classification(intents=["general"])

    logger.info("intents classified as %s (reply_language=%s)", classified.intents, classified.reply_language)
    if on_event is not None:
        on_event({"type": "step", "stage": "classified", **asdict(classified)})
    return classified


def run_general_chat(messages: list, on_event: OnEvent | None = None, depth: str | None = None,
                     language: str | None = None) -> ToolAnswer:
    """Plain conversational reply — no retrieval, no tool. The orchestrator's
    own built-in answer for whatever no registered tool covers, given the
    programme's current facts so that any fact it states is a checked one."""
    if on_event is not None:
        on_event({"type": "step", "stage": "answering", "agent": "supervisor"})

    chunks: list[str] = []
    facts = current_facts().text or "CURRENT PROGRAMME FACTS: not available right now — state no programme facts."
    prompt = reply_language.with_instruction(
        answer_depth.with_instruction(f"{SUPERVISOR_SYSTEM_PROMPT}\n\n{facts}", depth), language)
    for chunk in llm.stream(prompt, to_chat_messages(messages), temperature=0.7, max_tokens=answer_depth.max_tokens(depth, 2000)):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})

    return ToolAnswer(text="".join(chunks), agent_used="supervisor")
