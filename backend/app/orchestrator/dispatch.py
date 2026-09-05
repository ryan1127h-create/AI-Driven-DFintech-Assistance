"""
Dispatch — turns classified intents into an answer, entirely through the
Tool contract: an off-topic message gets a fixed decline (no tool, no LLM
call at all — see _route below for why); zero matched (in-scope) tools
falls back to plain conversation; one or more matched tools each produce a
draft (in parallel when there are several — Orchestrator-Workers), every
draft is checked by evaluate_branch_tool.py and, when it falls short,
fixed (a clarifying question, or one clean retry of that same tool), and
finally — only when there were 2+ drafts — synthesize_tool.py merges them
into one coherent reply. A single draft needs no merging, so it's returned
as-is: no synthesis call is spent on a no-op merge.

A new specialist becomes reachable here the moment it registers a Tool
with the right trigger_intents (see tools/registration.py) — this module
never names a specific tool, only ever looks one up by intent.
evaluate_branch/synthesize/localize are registered the same way, with no
trigger_intents (see tools/contracts.py::Tool.trigger_intents) — this
module calls them directly by name instead.

Per-draft evaluation (not a single whole-answer check) is deliberate:
Anthropic's own guidance on the Evaluator-Optimizer pattern is that it
works best with one clear criterion, and "does this draft cover the one
topic it was scoped to" is a much better-defined judgement than "does this
(possibly multi-topic, already-merged) answer cover everything" — the
latter is exactly the kind of fuzzy, multi-criterion judgement an LLM judge
gets wrong more often, and by the time something's already merged, there's
no way left to retry only the part that was actually missing.

After a final answer is produced, answer_turn() runs it through
localize_tool.py's reply-language conversion (a no-op unless the user's
question wasn't in English) before returning it.
"""

from __future__ import annotations

import concurrent.futures

from langchain_core.messages import AIMessage

from app.core.config import settings
from app.orchestrator import routing
from app.tools.contracts import OnEvent, ToolAnswer, registry
from app.tools.evaluate_branch_tool import EvaluateBranchInput
from app.tools.localize_tool import LocalizeInput
from app.tools.synthesize_tool import SynthesizeInput
from app.tools.turn_context import TurnState, last_human_message

_OFF_TOPIC_REPLY = (
    "I'm the assistant for the NUS MSc Digital Financial Technology (DFT) "
    "programme — I can only help with questions about the programme itself "
    "(admissions, courses, fees, career planning, comparisons with other "
    "programmes, etc.) or your own application/study journey. That question "
    "is outside what I can help with here. Is there anything about the DFT "
    "programme I can help you with instead?"
)

_ERROR_REPLY = (
    "Sorry, something went wrong while working on that. Please try asking "
    "again, or rephrase your question — if this keeps happening, it's best "
    "to contact the admissions office directly."
)


def _tool_name_for(intent: str) -> str | None:
    matches = registry.list_by_intent(intent)
    return matches[0].name if matches else None


def _route(intents: list[str]) -> tuple[str, list[str]]:
    """Returns (mode, tool_names): "decline" (out of scope, no tool, no LLM
    call), "general" (no tool matched, plain conversation), or "tools" (1
    or more tool names to run — _run_tools() below handles both the
    single-tool and multi-tool cases with the same code path).

    "decline" is checked first and short-circuits everything else: this
    assistant's whole purpose is the NUS MSc DFT programme (see
    routing.py's INTENT_CLASSIFIER_PROMPT), so a message classified
    off_topic never reaches a tool or even a generation call — the reply is
    a fixed string, which is also cheaper and more reliably on-scope than
    asking an LLM to decline politely every time.

    "off_topic" only forces a decline when it's the ONLY thing the
    classifier returned. Its own prompt promises never to combine
    off_topic with a genuine in-scope intent, but that promise is enforced
    by an instruction to the LLM, not by this code — if it's ever violated
    (a mixed message misjudged as partly off-topic), the in-scope
    intent(s) are still worth answering rather than discarding the whole
    turn over one classifier mistake."""
    valid = [i for i in intents if i in routing.VALID_INTENTS and i != "off_topic"]
    if "off_topic" in intents and not valid:
        return "decline", []
    if not valid:
        return "general", []

    if len(valid) == 1:
        name = _tool_name_for(valid[0])
        return ("tools", [name]) if name else ("general", [])

    fanout_names = [n for n in (_tool_name_for(i) for i in valid if i in routing.FANOUT_INTENTS) if n]
    if len(fanout_names) >= 2:
        return "tools", fanout_names
    if fanout_names:
        return "tools", fanout_names[:1]
    return "general", []


def _reply_with_sources(answer: ToolAnswer) -> str:
    reply = answer.text
    if answer.sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in answer.sources)
    return reply


def _evaluate_and_fix(
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
    that it's short of what it needs (see tools/contracts.py::
    ToolAnswer.needs_clarification) — or when the setting is off."""
    if draft.needs_clarification or not settings.enable_answer_evaluation:
        return draft

    try:
        verdict = registry.invoke_typed(
            "evaluate_branch",
            EvaluateBranchInput(intent=tool_name, user_message=user_message, draft_text=draft.text),
        )
    except Exception as exc:
        print(f"[dispatch] Warning: evaluating the {tool_name!r} draft failed, keeping it as-is — {exc}")
        return draft

    if verdict.action == "clarify":
        return ToolAnswer(text=verdict.note, agent_used=f"{draft.agent_used}+clarify", needs_clarification=True)

    if verdict.action == "retry":
        if on_event is not None:
            on_event({"type": "step", "stage": "revising", "agent": tool_name})
        try:
            retry_draft = registry.invoke_typed(tool_name, state, on_event=None)
        except Exception as exc:
            print(f"[dispatch] Warning: retrying {tool_name!r} failed, keeping the original draft — {exc}")
            return draft
        retry_draft.agent_used = f"{retry_draft.agent_used or tool_name}+revised"
        return retry_draft

    return draft  # "accept"


def _run_tools(tool_names: list[str], state: TurnState, on_event: OnEvent | None) -> ToolAnswer:
    """Runs 1+ tools, evaluates/fixes every draft, and merges when there
    were 2+ of them. A single tool streams live to the user exactly as
    before; 2+ tools run in parallel and silently (only the final merged
    reply streams) — both unchanged from before this draft/evaluate/fix
    step was added."""
    user_message = last_human_message(state.messages)

    if len(tool_names) == 1:
        name = tool_names[0]
        if on_event is not None:
            on_event({"type": "step", "stage": "answering", "agent": name})
        draft = registry.invoke_typed(name, state, on_event=on_event)
        if on_event is not None:
            on_event({"type": "step", "stage": "evaluating", "agent": name})
        return _evaluate_and_fix(name, state, user_message, draft, on_event)

    return _run_and_synthesize(tool_names, state, user_message, on_event)


def _run_and_synthesize(
    tool_names: list[str], state: TurnState, user_message: str, on_event: OnEvent | None,
) -> ToolAnswer:
    """
    Runs every matched tool in parallel (via a thread pool — these are
    independent blocking calls, and running them sequentially would
    multiply latency by the number of tools, defeating the point of
    "collaborating" specialists), evaluates and fixes each surviving draft,
    then merges them into one reply via synthesize_tool.py.

    Bounded by settings.dispatch_branch_timeout_seconds: whichever branches
    haven't settled by then are treated as "not ready" rather than blocking
    the whole reply indefinitely. Both thread pools here are deliberately
    NOT used as a context manager (`with ThreadPoolExecutor(...) as pool:`
    would call shutdown(wait=True) on exit and silently reintroduce an
    unbounded wait) — shutdown(wait=False) lets any still-running call
    finish on its own time without holding up this function's return.
    """
    if on_event is not None:
        on_event({"type": "step", "stage": "dispatch_start", "agents": tool_names})

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(tool_names))
    # Branches never stream to the user directly — their output is only
    # synthesis input — so on_event is left at None for each.
    future_to_name = {pool.submit(registry.invoke_typed, name, state, on_event=None): name for name in tool_names}
    done, not_done = concurrent.futures.wait(future_to_name, timeout=settings.dispatch_branch_timeout_seconds)

    results: dict[str, ToolAnswer] = {}
    for future in done:
        name = future_to_name[future]
        try:
            results[name] = future.result()
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": True})
        except Exception as exc:
            print(f"[dispatch] Warning: branch '{name}' failed — {exc}")
            results[name] = ToolAnswer(
                text="(no answer available for this part of the question)", agent_used=f"{name}_error"
            )
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": False})
    for future in not_done:
        name = future_to_name[future]
        print(f"[dispatch] Warning: branch '{name}' did not finish within {settings.dispatch_branch_timeout_seconds}s")
        results[name] = ToolAnswer(
            text="(this part of the answer wasn't ready in time — please ask again if you still need it)",
            agent_used=f"{name}_timeout",
        )
        if on_event is not None:
            on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": False, "timeout": True})
    pool.shutdown(wait=False)

    # If every single branch failed or timed out, there's nothing worth
    # evaluating or synthesizing — skip straight to a plain, honest reply.
    if all(a.agent_used.endswith(("_error", "_timeout")) for a in results.values()):
        return ToolAnswer(
            text="I wasn't able to look up any of what you asked this time — please try again in "
                 "a moment, or ask one part at a time.",
            agent_used="+".join(f"{name}_unavailable" for name in tool_names),
        )

    # Evaluate + fix every surviving (non-placeholder) branch, in parallel —
    # exactly the same _evaluate_and_fix() used for the single-tool case
    # above, just fanned out. A branch that already failed/timed out is
    # left untouched: it's already an honest placeholder, nothing to check.
    if on_event is not None:
        on_event({"type": "step", "stage": "evaluating"})
    eval_pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(tool_names))
    eval_future_to_name = {
        eval_pool.submit(_evaluate_and_fix, name, state, user_message, results[name], on_event): name
        for name in tool_names
        if not results[name].agent_used.endswith(("_error", "_timeout"))
    }
    for future in concurrent.futures.as_completed(eval_future_to_name):
        name = eval_future_to_name[future]
        try:
            results[name] = future.result()
        except Exception as exc:
            # Fail open: keep the original draft rather than losing this
            # branch entirely over an evaluation-step failure.
            print(f"[dispatch] Warning: evaluating/fixing branch '{name}' failed, keeping its original draft — {exc}")
    eval_pool.shutdown(wait=False)

    # Keep classification order (not completion order) so the synthesis
    # prompt sees drafts in a predictable, reproducible sequence.
    partials = [(name, results[name]) for name in tool_names]
    return registry.invoke_typed(
        "synthesize", SynthesizeInput(user_message=user_message, partials=partials), on_event=on_event,
    )


def answer_turn(state: TurnState, intents: list[str], on_event: OnEvent | None = None) -> tuple[AIMessage, str, str]:
    """Runs the turn's answer step given already-classified intents.
    Returns (ai_message, reply_text_with_sources, agent_used) — ai_message
    is the text only (what actually becomes conversation history);
    reply_text_with_sources is the same text plus a Sources footer, used
    for the API response / the streaming "done" event, never persisted
    back into history.

    `on_event` is a per-call concern, not part of the turn context itself
    — the same TurnState is reused across several tool invocations within
    one turn, each wanting a different value (a lone tool streams to the
    user; each multi-tool branch gets None since its output is only
    synthesis input). Streamed tokens are always in English regardless of
    state.reply_language — see orchestrator/localization.py, applied below
    only to the finished text, never to what's streamed mid-generation."""
    mode, tool_names = _route(intents)

    if mode == "decline":
        answer = ToolAnswer(text=_OFF_TOPIC_REPLY, agent_used="orchestrator_decline")
    elif mode == "general":
        try:
            answer = routing.run_general_chat(state.messages, on_event)
        except Exception as exc:
            print(f"[dispatch] Warning: general chat failed — {exc}")
            answer = ToolAnswer(text=_ERROR_REPLY, agent_used="orchestrator_error")
    else:
        # Nothing in _run_tools() is allowed to let an exception escape the
        # turn — any failure in tool/evaluation/synthesis code that wasn't
        # already caught closer to its source (a tool's own fallback, a
        # branch's per-future try/except, _evaluate_and_fix()'s own
        # try/excepts) becomes a graceful, in-persona reply instead of an
        # uncaught 500. This is the one place that last-resort safety net
        # has to live, since it's the single call site every tool_names
        # shape (one tool or several) funnels through.
        try:
            answer = _run_tools(tool_names, state, on_event)
        except Exception as exc:
            print(f"[dispatch] Warning: turn failed entirely (tools={tool_names}) — {exc}")
            answer = ToolAnswer(text=_ERROR_REPLY, agent_used="orchestrator_error")

    # Applies uniformly regardless of which branch above produced `answer`
    # — see localize_tool.py's own docstring for why this is a single final
    # step instead of being pushed into each prompt above. A no-op (no LLM
    # call) whenever state.reply_language is English/unset. Wrapped here
    # (rather than trusting the tool's own internal never-raise design
    # alone) because registry.invoke_typed() itself can still raise on a
    # hard timeout, one layer outside the handler's own try/except.
    try:
        answer = registry.invoke_typed(
            "localize",
            LocalizeInput(reply_language=state.reply_language, user_message=last_human_message(state.messages), answer=answer),
        )
    except Exception as exc:
        print(f"[dispatch] Warning: localize tool call failed, returning the answer as-is — {exc}")

    return AIMessage(content=answer.text), _reply_with_sources(answer), answer.agent_used
