"""
Localize — a Tool with no trigger_intents (see tools/contracts.py::
Tool.trigger_intents), called directly by name from
orchestrator/dispatch.py as the very last step of every turn: converts the
finished answer into the language the user actually asked in (see
tools/turn_context.py::TurnState.reply_language, detected once by
routing.py's intent classifier).

Every generation prompt in this app (RAG specialists, assessment, general
chat, evaluate_branch/synthesize) answers in English, unconditionally, with
no language instruction of its own. That's deliberate, not an oversight:
those prompts already carry a lot of domain-specific steering (retrieval
rules, hedging rules, structured sections) and burying one more
instruction — "oh, and reply in whatever language the user used" — inside
all of that is exactly the kind of thing that gets silently dropped once a
prompt is carrying enough other instructions. Keeping every business
prompt monolingual also means there's only one language this whole app's
prompt engineering has ever had to be evaluated in.

So instead this is a single, narrow, final conversion applied uniformly to
whatever text comes out the other end — a decline, an error message, a
clarifying question, a RAG answer, a synthesized multi-tool answer, it
doesn't matter which. dispatch.py calls this unconditionally, every turn;
"should a conversion actually happen" is decided inside the handler below,
by a plain code check on reply_language — never an LLM's own judgement call
(the same class of prompt-following failure above would apply just as well
to "decide for yourself whether to translate") — so a request that was
already in English costs nothing beyond the no-op check itself.

Streamed tokens during generation are always in English, unchanged — this
runs after generation finishes and produces the text that becomes the SSE
"done" event / the non-streaming response / what's persisted to history,
not something streamed token-by-token itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.adapters.deepseek_adapter import llm
from app.core.config import settings
from app.tools.contracts import OnEvent, Tool, ToolAnswer

_LOCALIZE_PROMPT = """\
Rewrite the assistant reply given below in {language} for a university \
programme assistant chatbot. This is a language conversion, not a summary \
or a rewrite of the content — keep every claim, hedge, and piece of advice \
exactly as strong or as soft as it was.

Preserve EXACTLY as-is, character for character — do not translate, \
reformat, recalculate, or reword any of these:
- Numbers, dates, fee amounts, and deadlines.
- Course codes (e.g. "FT5005") and programme/university names.
- URLs and the "Sources:" section at the end, if present.
- The Markdown structure (headings, bullet lists, bold text).

Match the tone and formality of the user's own message given below — do \
not default to a more formal or more casual register than they used.

Respond with ONLY the rewritten text — no preamble, no explanation, no \
notes about what you changed."""


class LocalizeInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    reply_language: str
    user_message: str
    answer: ToolAnswer


def _handler(inp: LocalizeInput, on_event: OnEvent | None = None) -> ToolAnswer:
    """Returns inp.answer unchanged whenever no conversion is needed
    (English, unset, or the setting is off) — the common, zero-cost case.
    Otherwise makes one LLM call and returns a new ToolAnswer with only
    `.text` replaced; `.sources`/`.agent_used`/`.needs_clarification` are
    carried over untouched. Never raises: a failed or empty conversion
    falls back to the original English answer rather than losing the turn
    — an English reply the user didn't ask for is a much smaller failure
    than no reply at all."""
    language = (inp.reply_language or "en").strip().lower()
    if language in ("en", "english", "") or not settings.enable_localization or not inp.answer.text:
        return inp.answer

    try:
        system_prompt = _LOCALIZE_PROMPT.format(language=language)
        payload = (
            f"User's message (for tone only, not to be answered again):\n{inp.user_message}\n\n"
            f"Text to rewrite into {language}:\n{inp.answer.text}"
        )
        rewritten = llm.complete(system_prompt, payload, temperature=0, max_tokens=4096).strip()
        if not rewritten:
            return inp.answer
        return ToolAnswer(
            text=rewritten, sources=inp.answer.sources, agent_used=inp.answer.agent_used,
            needs_clarification=inp.answer.needs_clarification,
        )
    except Exception as exc:
        print(f"[localize_tool] Warning: reply-language conversion to {language!r} failed, "
              f"returning the English answer — {exc}")
        return inp.answer


LOCALIZE_TOOL = Tool(
    name="localize",
    description="Converts the finished answer into the user's reply_language, preserving figures/codes/URLs/Markdown exactly.",
    input_model=LocalizeInput,
    handler=_handler,
    trigger_intents=frozenset(),
)
