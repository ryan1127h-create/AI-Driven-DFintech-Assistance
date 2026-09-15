"""
Knowledge QA's only LLM step: retrieve, build a tagged context, stream an
answer grounded strictly in that context. Shared by every fixed topic (see
service.py's registry) and by any caller supplying its own role prompt
(service.py::answer_with_role_prompt).

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
from app.domains.knowledge_retrieval.interface import build_context, cited_sources, retrieve

OnEvent = Callable[[dict], None]

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


def answer(
    role_prompt: str, user_message: str, chat_history: list[dict],
    *, filter_topics: set[str] | None = None, boost_topics: set[str] | None = None,
    on_event: OnEvent | None = None,
) -> tuple[str, list[str]]:
    """
    Core RAG step: retrieve (scoped by filter_topics/boost_topics), build a
    tagged context, call the LLM with `role_prompt` layered onto the shared
    rules above. Returns (answer_text, cited_sources).
    """
    if not user_message:
        return "I couldn't identify your question. Could you please rephrase it?", []

    hits = retrieve(user_message, top_k=5, filter_topics=filter_topics, boost_topics=boost_topics)
    context = build_context(hits) if hits else (
        "No specific programme information is currently available in the "
        "knowledge base. Please contact the admissions office directly."
    )

    system_prompt = _BASE_SYSTEM_PROMPT.format(role_prompt=role_prompt, context=context)
    # max_tokens is generous relative to the expected answer length as a
    # safety margin against truncation.
    chunks: list[str] = []
    for chunk in llm.stream(system_prompt, chat_history, temperature=0.2, max_tokens=2000):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})
    return "".join(chunks), cited_sources(hits)
