"""
Execution stage — runs the tool(s) routing.py matched, in parallel when
there are 2+ (Orchestrator-Workers), then hands each draft to evaluation.py
and, when there were 2+, the survivors to synthesis.py.
"""

from __future__ import annotations

import concurrent.futures

from app.core.config import settings
from app.core.resilience import run_with_timeout
from app.orchestrator.dispatch import evaluation, synthesis
from app.tools import contracts
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.turn_context import TurnState, last_human_message

# Matches the Tool.timeout_seconds default synthesis used before this stage
# was pulled out of the Tool/registry machinery.
_SYNTHESIS_TIMEOUT_SECONDS = 30.0


def run_tools(tool_names: list[str], state: TurnState, on_event: OnEvent | None) -> ToolAnswer:
    """Runs 1+ tools, evaluates/fixes every draft, and merges when there
    were 2+ of them. A single tool streams live to the user exactly as
    before; 2+ tools run in parallel and silently (only the final merged
    reply streams)."""
    user_message = last_human_message(state.messages)

    if len(tool_names) == 1:
        name = tool_names[0]
        if on_event is not None:
            on_event({"type": "step", "stage": "answering", "agent": name})
        draft = contracts.registry.invoke_typed(name, state, on_event=on_event)
        if on_event is not None:
            on_event({"type": "step", "stage": "evaluating", "agent": name})
        return evaluation.evaluate_and_fix(name, state, user_message, draft, on_event)

    return run_and_synthesize(tool_names, state, user_message, on_event)


def run_and_synthesize(
    tool_names: list[str], state: TurnState, user_message: str, on_event: OnEvent | None,
) -> ToolAnswer:
    """
    Runs every matched tool in parallel (via a thread pool — these are
    independent blocking calls, and running them sequentially would
    multiply latency by the number of tools, defeating the point of
    "collaborating" specialists), evaluates and fixes each surviving draft,
    then merges them into one reply via synthesis.py.

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
    future_to_name = {
        pool.submit(contracts.registry.invoke_typed, name, state, on_event=None): name for name in tool_names
    }
    done, not_done = concurrent.futures.wait(future_to_name, timeout=settings.dispatch_branch_timeout_seconds)

    results: dict[str, ToolAnswer] = {}
    for future in done:
        name = future_to_name[future]
        try:
            results[name] = future.result()
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": True})
        except Exception as exc:
            print(f"[execution] Warning: branch '{name}' failed — {exc}")
            results[name] = ToolAnswer(
                text="(no answer available for this part of the question)", agent_used=f"{name}_error"
            )
            if on_event is not None:
                on_event({"type": "step", "stage": "branch_done", "agent": name, "ok": False})
    for future in not_done:
        name = future_to_name[future]
        print(f"[execution] Warning: branch '{name}' did not finish within {settings.dispatch_branch_timeout_seconds}s")
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
    # exactly the same evaluation.evaluate_and_fix() used for the
    # single-tool case above, just fanned out. A branch that already
    # failed/timed out is left untouched: it's already an honest
    # placeholder, nothing to check.
    if on_event is not None:
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
        except Exception as exc:
            # Fail open: keep the original draft rather than losing this
            # branch entirely over an evaluation-step failure.
            print(f"[execution] Warning: evaluating/fixing branch '{name}' failed, keeping its original draft — {exc}")
    eval_pool.shutdown(wait=False)

    # Keep classification order (not completion order) so the synthesis
    # prompt sees drafts in a predictable, reproducible sequence.
    partials = [(name, results[name]) for name in tool_names]
    return run_with_timeout(
        lambda: synthesis.synthesize(
            synthesis.SynthesizeInput(user_message=user_message, partials=partials), on_event=on_event,
        ),
        _SYNTHESIS_TIMEOUT_SECONDS,
    )
