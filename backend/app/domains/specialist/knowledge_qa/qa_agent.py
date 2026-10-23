"""
Knowledge QA's LLM steps: turn the latest message into a standalone search
query, and stream an answer grounded strictly in what the caller passed in
— the programme's current facts and the reference material it retrieved
(the tools layer reads the data; this domain reads none itself). Shared by
every fixed topic (see service.py).

Takes plain, already-extracted inputs (a user_message string, chat_history
as plain role/content dicts) rather than LangChain message objects or a
Tool-layer OnEvent import — those conversions are the tools layer's job
(see app/tools/specialist/knowledge_qa_tool.py), not this domain's. `OnEvent` is
re-declared locally rather than imported from app.tools, for the same
reason app/tools/turn_context.py does: a domain may not import from the
tools layer (see app/.importlinter's top-level layers contract), so the
one shared shape — "a callback taking one event dict" — gets its own
local alias here instead.
"""

from __future__ import annotations

from collections.abc import Callable

from app.adapters.deepseek_adapter import llm
from app.core import answer_depth, reply_language
from app.core.logging import get_logger
from app.domains.specialist.knowledge_qa.facts import ENQUIRY_URL

logger = get_logger(__name__)

OnEvent = Callable[[dict], None]

_BASE_SYSTEM_PROMPT = """\
{role_prompt}

## Rule 1 — Answer ONLY from the supplied material
- Base your answer exclusively on the CURRENT PROGRAMME FACTS and the REFERENCE \
MATERIAL below. Do not use your own prior knowledge about NUS, this programme, or any \
other university.
- For the user's own situation, the user's record given as context in the \
conversation (their profile, application, application dates, degree progress) is \
supplied material too, and it is current: answer from it. If an earlier reply in \
this conversation said something wasn't available but the record now has it, answer \
from the record.
- If neither contains the answer, say plainly that the information is not in the \
available sources and point the user to the programme's enquiry form ({enquiry_url}). \
Never guess, never infer, never fill gaps with general knowledge.
- Reproduce all numbers, dates, amounts, deadlines and course codes exactly as they \
appear. Do not convert currencies or paraphrase figures.
- When it helps the user (e.g. what a 40% rebate leaves to pay), you may do a simple \
calculation on the stated figures — one step: add, subtract, multiply, divide, or take a \
percentage. Show the working ("40% of S$76,409 is S$30,563.60") and call the result an \
estimate.

## Rule 2 — Which intake
- Applicants are applying now for the intake the CURRENT PROGRAMME FACTS name. For \
fees, application dates and requirements, give those facts.
- Reference material may still hold an earlier intake's figures. Where it differs from \
the current facts, follow the current facts and do not repeat the older figure unless \
the user asks about that earlier intake.
- If the only information on a point is dated to an earlier intake or year, say which \
intake or year it is for.

## Rule 3 — Distinguish official policy from advisory guidance
- Material tagged [official] is official programme information. State it directly.
- Material tagged [advisory] is guidance compiled by this project, not official policy. \
You MUST hedge it with wording such as "we suggest", "as a guide", "you may consider", \
and make clear it is a recommendation rather than an official requirement.
- Never present advisory content as an official rule or requirement.

## Rule 4 — When sources disagree
- ⚠️GOVERNS marks the source to follow on that specific point.
- ⚠️SUPERSEDED marks a source overridden only on that specific point — its other \
content, and its own figures, are still valid and should still be given to the user, \
just reframed as reference points rather than hard requirements.
- Never expose this internal tagging to the user — refer to where information comes \
from in plain language (e.g. "the programme FAQ states ...").

## Rule 5 — Style
- Be accurate, concise, and professional.
- Do not write filler like "according to the reference material".

{facts}

Reference material:
{context}
"""

_NO_FACTS = "CURRENT PROGRAMME FACTS: not available for this answer — rely on the reference material."
_NO_CONTEXT = "No specific programme information was found in the knowledge base for this question."

_QUERY_PROMPT = """\
Rewrite the user's latest message as one standalone English search query for a \
knowledge base about the NUS MSc Digital Financial Technology programme (admissions, \
fees, courses, capstone, FAQ). Resolve references to earlier turns ("that", "what about \
part-time?") using the conversation, translate to English if needed, and keep course \
codes, numbers and names as written. Reply with the query only."""


def search_query(user_message: str, chat_history: list[dict]) -> str:
    """The query to retrieve with: the message itself when it is English and
    the first turn, else a standalone English rewrite of it (retrieval sees
    only the query, and most of the material is English). Falls back to the
    message on any failure."""
    # Earlier turns only: the latest message is the last entry, and system
    # entries (profile, summaries) are not part of the conversation.
    earlier = [m for m in chat_history[:-1] if m.get("role") in ("user", "assistant") and m.get("content")]
    if not earlier and user_message.isascii():
        return user_message
    transcript = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in earlier[-4:])
    payload = f"Conversation so far:\n{transcript or '(none)'}\n\nLatest message:\n{user_message}"
    try:
        query = llm.complete(_QUERY_PROMPT, payload, temperature=0, max_tokens=80).strip().strip('"')
    except Exception:
        logger.exception("knowledge qa: rewriting the search query failed, using the message")
        return user_message
    return query or user_message


def answer(
    role_prompt: str, user_message: str, chat_history: list[dict],
    *, context: str | None, facts: str | None = None, on_event: OnEvent | None = None,
    depth: str | None = None, language: str | None = None,
) -> str:
    """
    Core generation step: call the LLM with `role_prompt` layered onto the
    shared rules above, the programme's current `facts` and the caller's
    reference `context` (None = nothing was found), written in the reply
    `language` (None: the user's message's). Streams tokens through
    `on_event` when given. Returns the answer text.
    """
    system_prompt = reply_language.with_instruction(answer_depth.with_instruction(
        _BASE_SYSTEM_PROMPT.format(role_prompt=role_prompt, enquiry_url=ENQUIRY_URL,
                                   facts=facts or _NO_FACTS, context=context or _NO_CONTEXT),
        depth,
    ), language)
    # max_tokens is generous relative to the expected answer length as a
    # safety margin against truncation.
    chunks: list[str] = []
    for chunk in llm.stream(system_prompt, chat_history, temperature=0.2, max_tokens=answer_depth.max_tokens(depth, 2000)):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})
    return "".join(chunks)
