"""
Dispatch — turns classified intents into an answer, entirely through the
Tool contract: zero matched tools falls back to plain conversation, one
matched tool answers directly (streamed straight to the user), two or more
run in parallel and get merged by one synthesis call (Orchestrator-Workers).

A new specialist becomes reachable here the moment it registers a Tool
with the right trigger_intents (see tools/registration.py) — this module
never names a specific tool, only ever looks one up by intent.
"""

from __future__ import annotations

import concurrent.futures

from langchain_core.messages import AIMessage

from app.adapters.deepseek_adapter import llm
from app.core.config import settings
from app.orchestrator import routing
from app.tools.contracts import OnEvent, ToolAnswer, registry
from app.tools.turn_context import TurnState, last_human_message

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


def _tool_name_for(intent: str) -> str | None:
    matches = registry.list_by_intent(intent)
    return matches[0].name if matches else None


def _route(intents: list[str]) -> tuple[str, list[str]]:
    """Returns (mode, tool_names): "general" (no tool), "single" (exactly
    one tool name), or "dispatch" (2+ tool names to fan out to)."""
    valid = [i for i in intents if i in routing.VALID_INTENTS]
    if not valid:
        return "general", []

    if len(valid) == 1:
        name = _tool_name_for(valid[0])
        return ("single", [name]) if name else ("general", [])

    fanout_names = [n for n in (_tool_name_for(i) for i in valid if i in routing.FANOUT_INTENTS) if n]
    if len(fanout_names) >= 2:
        return "dispatch", fanout_names
    if fanout_names:
        return "single", fanout_names[:1]
    return "general", []


def _reply_with_sources(answer: ToolAnswer) -> str:
    reply = answer.text
    if answer.sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in answer.sources)
    return reply


def _invoke_single(tool_name: str, state: TurnState, on_event: OnEvent | None) -> ToolAnswer:
    if on_event is not None:
        on_event({"type": "step", "stage": "answering", "agent": tool_name})
    return registry.invoke_typed(tool_name, state, on_event=on_event)


def _dispatch_many(tool_names: list[str], state: TurnState, on_event: OnEvent | None) -> ToolAnswer:
    """
    Runs every matched tool in parallel (via a thread pool — these are
    independent blocking calls, and running them sequentially would
    multiply latency by the number of tools, defeating the point of
    "collaborating" specialists), then merges the partial answers into one
    reply with a single synthesis LLM call.

    Bounded by settings.dispatch_branch_timeout_seconds: whichever branches
    haven't settled by then are treated as "not ready" rather than blocking
    the whole reply indefinitely. The executor is deliberately NOT used as
    a context manager (`with ThreadPoolExecutor(...) as pool:` would call
    shutdown(wait=True) on exit and silently reintroduce the same unbounded
    wait) — shutdown(wait=False) lets any still-running branch finish on
    its own time without holding up this function's return.
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

    # Keep classification order (not completion order) so the synthesis
    # prompt sees drafts in a predictable, reproducible sequence.
    partials = [(name, results[name]) for name in tool_names]
    drafts = "\n\n".join(f"[{answer.agent_used or name} draft]\n{answer.text}" for name, answer in partials)
    last_user_message = last_human_message(state.messages)

    if on_event is not None:
        on_event({"type": "step", "stage": "synthesizing"})

    synthesis_prompt = _SYNTHESIS_PROMPT.format(drafts=drafts)
    chunks: list[str] = []
    for chunk in llm.stream(synthesis_prompt, [{"role": "user", "content": last_user_message}], temperature=0.2, max_tokens=2000):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})
    reply = "".join(chunks)

    seen: set[str] = set()
    sources: list[str] = []
    for _, answer in partials:
        for s in answer.sources:
            if s not in seen:
                seen.add(s)
                sources.append(s)

    agent_used = "+".join(answer.agent_used or name for name, answer in partials)
    return ToolAnswer(text=reply, sources=sources, agent_used=agent_used)


def answer_turn(state: TurnState, intents: list[str], on_event: OnEvent | None = None) -> tuple[AIMessage, str, str]:
    """Runs the turn's answer step given already-classified intents.
    Returns (ai_message, reply_text_with_sources, agent_used) — ai_message
    is the text only (what actually becomes conversation history);
    reply_text_with_sources is the same text plus a Sources footer, used
    for the API response / the streaming "done" event, never persisted
    back into history.

    `on_event` is a per-call concern, not part of the turn context itself
    — the same TurnState is reused across several tool invocations within
    one dispatch, each wanting a different value (the sole tool streams to
    the user; each dispatch branch gets None since its output is only
    synthesis input)."""
    mode, tool_names = _route(intents)

    if mode == "general":
        answer = routing.run_general_chat(state.messages, on_event)
    elif mode == "single":
        answer = _invoke_single(tool_names[0], state, on_event)
    else:
        answer = _dispatch_many(tool_names, state, on_event)

    return AIMessage(content=answer.text), _reply_with_sources(answer), answer.agent_used
