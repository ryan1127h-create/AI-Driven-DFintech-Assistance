"""
Execution stage — runs the tool(s) routing.py matched, in parallel when
there are 2+ (Orchestrator-Workers), then hands each draft to evaluation.py
and, when there were 2+, joins the survivors with merge.py.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import replace

from app.core.config import settings
from app.core.logging import get_logger
from app.orchestrator.dispatch import evaluation, merge
from app.tools import contracts
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.turn_context import TurnState, last_human_message

logger = get_logger(__name__)


def run_tools(tool_names: list[str], state: TurnState, on_event: OnEvent | None) -> ToolAnswer:
    """Runs 1+ tools, evaluates/fixes every draft, and joins them when
    there were 2+. A single tool streams live to the user; 2+ tools run in
    parallel and silently, and the joined reply is sent once they're all
    done."""
    user_message = last_human_message(state.messages)

    if len(tool_names) == 1:
        name = tool_names[0]
        if on_event is not None:
            on_event({"type": "step", "stage": "answering", "agent": name})
        draft = contracts.registry.invoke_typed(name, state, on_event=on_event)
        if on_event is not None and evaluation.will_evaluate(name, draft):
            on_event({"type": "step", "stage": "evaluating", "agent": name})
        return evaluation.evaluate_and_fix(name, state, user_message, draft, on_event)

    return run_and_merge(tool_names, state, user_message, on_event)


def run_and_merge(
    tool_names: list[str], state: TurnState, user_message: str, on_event: OnEvent | None,
) -> ToolAnswer:
    """
    Runs every matched tool in parallel (via a thread pool — these are
    independent blocking calls, and running them sequentially would
    multiply latency by the number of tools), evaluates and fixes each
    surviving draft, then joins them in classification order (merge.py).

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
    # Branches never stream to the user directly — their output is joined
    # first — so on_event is left at None for each. Each branch learns which
    # other tools answer the same message, so it keeps to its own part.
    future_to_name = {
        pool.submit(contracts.registry.invoke_typed, name,
                    replace(state, other_tools=tuple(n for n in tool_names if n != name)), on_event=None): name
        for name in tool_names
    }
    done, not_done = concurrent.futures.wait(future_to_name, timeout=settings.dispatch_branch_timeout_seconds)

    results: dict[str, ToolAnswer] = {}
    for future in done:
        name = future_to_name[future]
        try:
            results[name] = future.result()
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": True})
        except Exception:
            logger.exception("branch %s failed", name)
            results[name] = ToolAnswer(
                text="(no answer available for this part of the question)", agent_used=f"{name}_error"
            )
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": False})
    for future in not_done:
        name = future_to_name[future]
        logger.warning("branch %s did not finish within %ss", name, settings.dispatch_branch_timeout_seconds)
        results[name] = ToolAnswer(
            text="(this part of the answer wasn't ready in time — please ask again if you still need it)",
            agent_used=f"{name}_timeout",
        )
        if on_event is not None:
            on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": False, "timeout": True})
    pool.shutdown(wait=False)

    # If every single branch failed or timed out, there's nothing worth
    # evaluating or joining — skip straight to a plain, honest reply.
    if all(a.agent_used.endswith(("_error", "_timeout")) for a in results.values()):
        return ToolAnswer(
            text="I wasn't able to look up any of what you asked this time — please try again in "
                 "a moment, or ask one part at a time.",
            agent_used="+".join(f"{name}_unavailable" for name in tool_names),
        )

    # Evaluate + fix every surviving (non-placeholder) branch, in parallel —
    # exactly the same evaluation.evaluate_and_fix() used for the
    # single-tool case above, just fanned out. A branch that already
    # failed/timed out is left untouched: it's already an honest
    # placeholder, nothing to check.
    if on_event is not None and any(evaluation.will_evaluate(name, results[name]) for name in tool_names):
        on_event({"type": "step", "stage": "evaluating"})
    eval_pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(tool_names))
    eval_future_to_name = {
        eval_pool.submit(evaluation.evaluate_and_fix, name, state, user_message, results[name], on_event): name
        for name in tool_names
        if not results[name].agent_used.endswith(("_error", "_timeout"))
    }
    for future in concurrent.futures.as_completed(eval_future_to_name):
        name = eval_future_to_name[future]
        try:
            results[name] = future.result()
        except Exception:
            # Fail open: keep the original draft rather than losing this
            # branch entirely over an evaluation-step failure.
            logger.exception("evaluating branch %s failed, keeping its original draft", name)
    eval_pool.shutdown(wait=False)

    # Classification order, not completion order: a predictable reply.
    answer = merge.merge([(name, results[name]) for name in tool_names])
    if on_event is not None and answer.text:
        on_event({"type": "token", "text": answer.text})
    return answer
