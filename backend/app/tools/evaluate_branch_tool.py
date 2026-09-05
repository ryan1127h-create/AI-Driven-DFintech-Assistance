"""
Evaluate-branch — a Tool with no trigger_intents, called directly by name
(see tools/contracts.py::Tool.trigger_intents: "empty for a tool that's
only ever called directly, never routed to by intent classification") from
orchestrator/dispatch.py, once per produced draft — whether there's only
one (a "single"-mode turn) or several running in parallel (a "dispatch"-
mode turn). Registering this alongside every chatbot-facing specialist
means there's exactly one way anything in this app gets invoked
(registry.invoke_typed by name), evaluation included, instead of a special
carve-out for it.

Judges ONE draft against the specific intent it was scoped to answer —
never the user's whole (possibly multi-part) question, and never other
drafts. That narrower scope is deliberate: Anthropic's own guidance on the
Evaluator-Optimizer pattern is that it works best with one clear evaluation
criterion, and "does this draft cover its own topic" is a much more
well-defined judgement than "does this merged answer cover everything" —
the latter is exactly the kind of fuzzy, multi-criterion judgement an LLM
judge gets wrong more often. dispatch.py is responsible for calling this
once per draft and deciding what to do with an insufficient one (see its
own module docstring).

Never raises: a failed or malformed evaluation call defaults to "accept" —
the draft goes out as produced rather than blocking the turn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.adapters.deepseek_adapter import llm
from app.tools.contracts import OnEvent, Tool

_EVAL_PROMPT = """\
You are reviewing one specialist's draft answer, as part of answering a \
user's question for the NUS MSc Digital Financial Technology (DFT) \
programme assistant. The user's question may have several parts; this \
draft was produced by the "{intent}" specialist and is only responsible \
for the "{intent}"-related part.

Judge ONLY whether the draft adequately covers that part — not tone, \
length, or phrasing, and not whether it addresses OTHER parts of the \
question (other specialists handle those separately; that's not this \
draft's job).

Respond with ONLY a JSON object, one of:
{{"action": "accept"}}
{{"action": "clarify", "note": "<one short question to ask the user, scoped to what's missing>"}}
{{"action": "retry", "note": "<one short sentence describing the gap, for logging only>"}}

Use "clarify" only when this part genuinely cannot be answered without \
more information FROM THE USER (not from a database the system already has \
access to). Use "retry" when the draft is incomplete in a way a fresh \
attempt could plausibly fix. When in doubt, prefer "accept" — this check \
should rarely override a reasonable draft."""


@dataclass
class BranchVerdict:
    action: Literal["accept", "clarify", "retry"] = "accept"
    # clarify: the question to ask the user, verbatim. retry: a short gap
    # description, informational only — never fed back into the retried
    # tool's own context (see dispatch.py for why: injecting "your previous
    # attempt failed because X" into a retry contaminates its context and
    # tends to confuse rather than help; a retry is a clean, independent
    # rerun instead).
    note: str = ""


class EvaluateBranchInput(BaseModel):
    intent: str
    user_message: str
    draft_text: str


def _handler(inp: EvaluateBranchInput, on_event: OnEvent | None = None) -> BranchVerdict:
    if not inp.user_message or not inp.draft_text:
        return BranchVerdict()

    try:
        payload = f"User's question:\n{inp.user_message}\n\nDraft answer:\n{inp.draft_text}"
        prompt = _EVAL_PROMPT.format(intent=inp.intent)
        raw = llm.complete(prompt, payload, temperature=0, max_tokens=300)
        result = json.loads(raw.strip())
        action = result.get("action", "accept")
        if action not in ("accept", "clarify", "retry"):
            return BranchVerdict()
        if action == "accept":
            return BranchVerdict()
        note = result.get("note", "")
        if not isinstance(note, str) or not note.strip():
            return BranchVerdict()  # a clarify/retry with no usable note isn't actionable
        return BranchVerdict(action=action, note=note.strip())
    except Exception as exc:
        print(f"[evaluate_branch] Warning: evaluation of the {inp.intent!r} draft failed, "
              f"defaulting to accept — {exc}")
        return BranchVerdict()


EVALUATE_BRANCH_TOOL = Tool(
    name="evaluate_branch",
    description="Judges whether one specialist's draft adequately covers the part of the question it was scoped to answer.",
    input_model=EvaluateBranchInput,
    handler=_handler,
    trigger_intents=frozenset(),
)
