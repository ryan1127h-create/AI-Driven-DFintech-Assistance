"""
Evaluation stage — judges one specialist's draft against the intent it was
scoped to, and applies the verdict (accept/clarify/retry). Runs once per
produced draft, whether there's only one (a "single"-mode turn) or several
running in parallel (a "dispatch"-mode turn) — see execution.py.

Judges ONE draft against the specific intent it was scoped to answer —
never the user's whole (possibly multi-part) question, and never other
drafts. That narrower scope is deliberate: Anthropic's own guidance on the
Evaluator-Optimizer pattern is that it works best with one clear evaluation
criterion, and "does this draft cover the one topic it was scoped to" is a
much better-defined judgement than "does this (possibly multi-topic,
already-merged) answer cover everything" — the latter is exactly the kind
of fuzzy, multi-criterion judgement an LLM judge gets wrong more often, and
by the time something's already merged, there's no way left to retry only
the part that was actually missing.

Not a registered Tool (unlike the domain-backed specialists this evaluates)
— trigger_intents would always be empty since this is only ever called
directly, once per draft, from execution.py, never routed to by intent
classification. Keeping it a plain function makes that explicit instead of
carrying Tool fields (input_model, fallback, trigger_intents) that would
never be used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from app.adapters.deepseek_adapter import llm
from app.core.config import settings
from app.core.resilience import run_with_timeout
from app.tools import contracts
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.turn_context import TurnState

# Matches the Tool.timeout_seconds default every registered tool used
# before this stage was pulled out of the Tool/registry machinery.
_TIMEOUT_SECONDS = 30.0

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
    # tool's own context (see evaluate_and_fix() below for why: injecting
    # "your previous attempt failed because X" into a retry contaminates
    # its context and tends to confuse rather than help; a retry is a
    # clean, independent rerun instead).
    note: str = ""


@dataclass
class EvaluateBranchInput:
    intent: str
    user_message: str
    draft_text: str


def evaluate_branch(inp: EvaluateBranchInput, on_event: OnEvent | None = None) -> BranchVerdict:
    """Never raises: a failed or malformed evaluation call defaults to
    "accept" — the draft goes out as produced rather than blocking the
    turn."""
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
        print(f"[evaluation] Warning: evaluation of the {inp.intent!r} draft failed, "
              f"defaulting to accept — {exc}")
        return BranchVerdict()


def evaluate_and_fix(
    tool_name: str, state: TurnState, user_message: str, draft: ToolAnswer, on_event: OnEvent | None,
) -> ToolAnswer:
    """Runs evaluate_branch on one draft and applies its verdict:
    "accept" (unchanged), "clarify" (replaced with a targeted question), or
    "retry" (one clean rerun of the same tool — with on_event=None even
    when the original call streamed live, so a retry's tokens never get
    appended after an already-fully-streamed first draft; the corrected
    text only ever reaches the user via the final SSE "done" event, the
    same "produce, then possibly replace" mechanic localization.py already
    uses). Never a second evaluation of the retry — bounded to at most one
    retry, no matter what.

    Skipped entirely (no LLM call) when the draft already came back with
    needs_clarification=True — a tool that already knows, deterministically,
    that it's short of what it needs (see app/tools/contracts.py::
    ToolAnswer.needs_clarification) — or when the setting is off."""
    if draft.needs_clarification or not settings.enable_answer_evaluation:
        return draft

    try:
        verdict = run_with_timeout(
            lambda: evaluate_branch(
                EvaluateBranchInput(intent=tool_name, user_message=user_message, draft_text=draft.text)
            ),
            _TIMEOUT_SECONDS,
        )
    except Exception as exc:
        print(f"[evaluation] Warning: evaluating the {tool_name!r} draft failed, keeping it as-is — {exc}")
        return draft

    if verdict.action == "clarify":
        return ToolAnswer(text=verdict.note, agent_used=f"{draft.agent_used}+clarify", needs_clarification=True)

    if verdict.action == "retry":
        if on_event is not None:
            on_event({"type": "step", "stage": "revising", "agent": tool_name})
        try:
            retry_draft = contracts.registry.invoke_typed(tool_name, state, on_event=None)
        except Exception as exc:
            print(f"[evaluation] Warning: retrying {tool_name!r} failed, keeping the original draft — {exc}")
            return draft
        retry_draft.agent_used = f"{retry_draft.agent_used or tool_name}+revised"
        return retry_draft

    return draft  # "accept"
