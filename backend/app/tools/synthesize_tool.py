"""
Synthesize — a Tool with no trigger_intents, called directly by name (see
tools/contracts.py::Tool.trigger_intents for that convention) from
orchestrator/dispatch.py, exactly once per "dispatch"-mode turn (2+
specialist drafts running in parallel) — never for a "single"-mode turn,
where there's only one draft and nothing to merge, so dispatch.py just
returns it directly instead of spending an LLM call on a merge that would
be a no-op.

This is the Orchestrator-Workers pattern's "combine the workers' results"
step, pulled out into its own Tool rather than living inline in
dispatch.py — registering it the same way as every chatbot-facing
specialist means there's exactly one calling convention
(registry.invoke_typed) for everything this app ever invokes, evaluation
and synthesis included, instead of special-casing the orchestration
plumbing.

By the time dispatch.py calls this, every draft has already been through
evaluate_branch_tool.py and, where needed, a clean retry or a clarifying-
question replacement (see dispatch.py's own docstring) — so this never
has to reason about whether a draft is any good, only about how to weave
already-trustworthy drafts into one reply.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.adapters.deepseek_adapter import llm
from app.tools.contracts import OnEvent, Tool, ToolAnswer

_SYNTHESIS_PROMPT = """\
The user's message touched on multiple topics. Below are draft answers from \
different specialist advisors, each covering one part of the question.

Combine them into a single, coherent reply that:
- Answers every part of the user's original question.
- Does not repeat the same information in multiple places.
- Reads naturally, not like a list of disconnected fragments stitched together.
- Preserves every fact, figure, date, and hedging/advisory wording EXACTLY as \
given in the drafts below — do not invent, drop, soften, or "correct" anything.
- Replies in the same language the user's question was asked in.

Do not mention that this answer was assembled from multiple drafts or advisors. \
The drafts below may contain internal citation markers such as "SOURCE 1", \
"[official]", "[advisory]", "⚠️GOVERNS", or "⚠️SUPERSEDED" — these are for your \
reference only. Never reproduce them in your reply; rephrase whatever they were \
attached to in plain language instead (e.g. "the programme FAQ states ..." \
rather than "according to SOURCE 1 [advisory]").

{drafts}
"""


class SynthesizeInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_message: str
    # Ordered (name, answer) pairs — classification order, not completion
    # order, so the synthesis prompt sees drafts in a predictable,
    # reproducible sequence regardless of which branch finished first.
    partials: list[tuple[str, ToolAnswer]]


def _handler(inp: SynthesizeInput, on_event: OnEvent | None = None) -> ToolAnswer:
    drafts = "\n\n".join(f"[{answer.agent_used or name} draft]\n{answer.text}" for name, answer in inp.partials)
    prompt = _SYNTHESIS_PROMPT.format(drafts=drafts)

    chunks: list[str] = []
    for chunk in llm.stream(prompt, [{"role": "user", "content": inp.user_message}], temperature=0.2, max_tokens=2000):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})
    reply = "".join(chunks)

    seen: set[str] = set()
    sources: list[str] = []
    for _, answer in inp.partials:
        for s in answer.sources:
            if s not in seen:
                seen.add(s)
                sources.append(s)

    agent_used = "+".join(answer.agent_used or name for name, answer in inp.partials)
    return ToolAnswer(text=reply, sources=sources, agent_used=agent_used)


SYNTHESIZE_TOOL = Tool(
    name="synthesize",
    description="Merges 2+ already-verified specialist drafts into one coherent reply.",
    input_model=SynthesizeInput,
    handler=_handler,
    trigger_intents=frozenset(),
)
