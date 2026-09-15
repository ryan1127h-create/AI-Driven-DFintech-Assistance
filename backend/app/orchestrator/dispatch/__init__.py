"""
Dispatch — turns classified intents into an answer. One module per
workflow stage, run in order by answer_turn() below:

    routing.py        — decide decline / general / which tool(s) to run
    requirements.py       — gate: block the whole batch until every
                             matched tool's required input is present
    execution.py             — run the matched tool(s), in parallel when 2+
    evaluation.py                — judge and, where needed, fix each draft
    synthesis.py                    — merge 2+ evaluated drafts into one reply
    localization.py                     — convert the finished answer into
                                           the user's reply language

An off-topic message gets a fixed decline (no tool, no LLM call at all —
see routing.py for why); zero matched (in-scope) tools falls back to plain
conversation; one or more matched tools are first checked by
requirements.py — if any of them is missing something it deterministically
needs from the user, none of them run this turn, and a single consolidated
request for what's missing is returned instead (see requirements.py for
why this is all-or-nothing rather than per-tool). Otherwise each matched
tool produces a draft (in parallel when there are several —
Orchestrator-Workers), every draft is checked by evaluation.py and, when it
falls short, fixed (a clarifying question, or one clean retry of that same
tool), and finally — only when there were 2+ drafts — synthesis.py merges
them into one coherent reply. A single draft needs no merging, so it's
returned as-is: no synthesis call is spent on a no-op merge.

A new specialist becomes reachable here the moment it registers a Tool
with the right trigger_intents (see app/tools/registration.py) — routing.py
never names a specific tool, only ever looks one up by intent.
evaluation/synthesis/localization are NOT registered Tools (see
evaluation.py's own module docstring for why) — this package calls them
directly, as plain functions.

answer_turn() is the only thing anything outside this package calls (see
orchestrator/turn_service.py).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.core.resilience import run_with_timeout
from app.orchestrator import classification
from app.orchestrator.dispatch import execution, localization, requirements, routing
from app.tools.contracts import OnEvent, ToolAnswer
from app.tools.turn_context import TurnState, last_human_message

# Matches the Tool.timeout_seconds default localization used before this
# stage was pulled out of the Tool/registry machinery.
_LOCALIZE_TIMEOUT_SECONDS = 30.0

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


def _reply_with_sources(answer: ToolAnswer) -> str:
    reply = answer.text
    if answer.sources:
        reply += "\n\nSources:\n" + "\n".join(f"- {s}" for s in answer.sources)
    return reply


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
    state.reply_language — see localization.py, applied below only to the
    finished text, never to what's streamed mid-generation."""
    mode, tool_names = routing.route(intents)

    if mode == "decline":
        answer = ToolAnswer(text=_OFF_TOPIC_REPLY, agent_used="orchestrator_decline")
    elif mode == "general":
        try:
            answer = classification.run_general_chat(state.messages, on_event)
        except Exception as exc:
            print(f"[dispatch] Warning: general chat failed — {exc}")
            answer = ToolAnswer(text=_ERROR_REPLY, agent_used="orchestrator_error")
    else:
        # requirements.check_requirements() never raises (see its own
        # docstring), so it's safe to call outside the try/except below —
        # the same treatment routing.route() already gets.
        gate = requirements.check_requirements(tool_names, state)
        if not gate.ready:
            answer = requirements.build_need_input_answer(gate)
        else:
            # Nothing in execution.run_tools() is allowed to let an
            # exception escape the turn — any failure in tool/evaluation/
            # synthesis code that wasn't already caught closer to its
            # source (a tool's own fallback, a branch's per-future
            # try/except, evaluate_and_fix()'s own try/excepts) becomes a
            # graceful, in-persona reply instead of an uncaught 500. This
            # is the one place that last-resort safety net has to live,
            # since it's the single call site every tool_names shape (one
            # tool or several) funnels through.
            try:
                answer = execution.run_tools(tool_names, state, on_event)
            except Exception as exc:
                print(f"[dispatch] Warning: turn failed entirely (tools={tool_names}) — {exc}")
                answer = ToolAnswer(text=_ERROR_REPLY, agent_used="orchestrator_error")

    # Applies uniformly regardless of which branch above produced `answer`
    # — see localization.py's own docstring for why this is a single final
    # step instead of being pushed into each prompt above. A no-op (no LLM
    # call) whenever state.reply_language is English/unset. Wrapped in
    # run_with_timeout here (rather than trusting localize()'s own
    # internal never-raise design alone) because a hard timeout is still
    # possible one layer outside its own try/except — on any failure,
    # `answer` simply keeps its pre-localization value.
    try:
        answer = run_with_timeout(
            lambda: localization.localize(localization.LocalizeInput(
                reply_language=state.reply_language,
                user_message=last_human_message(state.messages),
                answer=answer,
            )),
            _LOCALIZE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        print(f"[dispatch] Warning: localize call failed, returning the answer as-is — {exc}")

    return AIMessage(content=answer.text), _reply_with_sources(answer), answer.agent_used
