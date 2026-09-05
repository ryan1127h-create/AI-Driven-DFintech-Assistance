"""
The Tool contract — the one shape every registered capability exposes,
whether it's a single utility function or an entire domain's workflow. A
Tool's handler is a plain, synchronous callable with no framework
dependency, so it can be unit-tested by calling it directly with a
constructed input — no FastAPI, no database, unless the handler itself
needs one.

Every handler accepts an `on_event` keyword — a callback for streaming
progress/token events (see core/logging.py's correlation-id middleware for
the same "optional, ignored when absent" convention). A tool being run as
the orchestrator's sole answer to a turn is called with a real callback so
its answer streams to the user as it's produced; a tool running as one
branch of a multi-tool dispatch is called with on_event=None, since its
output is only a draft the orchestrator synthesizes further — never shown
to the user verbatim.

Domains and shared utilities register themselves into the module-level
`registry` at import time; the orchestrator (and anything else that wants
to call a tool by name) only ever reads from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Type

from pydantic import BaseModel

from app.core.resilience import run_with_timeout

OnEvent = Callable[[dict], None]
ToolHandler = Callable[..., Any]  # (input, *, on_event: OnEvent | None = None) -> Any


@dataclass
class ToolAnswer:
    """The shape a natural-language-answering tool (a RAG specialist, an
    LLM-backed domain integration) returns — enough for the orchestrator to
    merge several of these into one reply and log which path actually
    produced it."""

    text: str
    sources: list[str] = field(default_factory=list)
    # Which implementation actually answered — usually the tool's own name,
    # but may differ when a tool degraded to a fallback path internally
    # (e.g. "career_agent_fallback" when the primary integration raised).
    agent_used: str = ""
    # Set by a handler that already knows, deterministically, that it's
    # short of what it needs from the user (not from a database it already
    # has) rather than guessing an answer — e.g. a career-plan request with
    # no target role and no profile on file. The orchestrator's post-answer
    # evaluation step (orchestrator/evaluation.py) treats this as a signal
    # to skip its own LLM judgement entirely: the tool already knows more
    # cheaply and more reliably than a second LLM call re-guessing it would.
    needs_clarification: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: Type[BaseModel]
    handler: ToolHandler
    timeout_seconds: float = 30.0
    # Called with the same input (and on_event) if the handler times out or
    # raises. Left unset, the failure just propagates — appropriate for a
    # tool where there's no meaningful degraded answer to give instead of
    # failing outright.
    fallback: ToolHandler | None = None
    # Which orchestrator-recognized intents this tool answers. Empty for a
    # tool that's only ever called directly (by name), never routed to by
    # intent classification.
    trigger_intents: frozenset[str] = field(default_factory=frozenset)


class ToolNotFoundError(Exception):
    """Raised when the registry is asked for a tool name nothing ever
    registered."""


class ToolRegistry:
    """In-process registry of every Tool the running app knows about."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"a tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(name) from None

    def list_by_intent(self, intent: str) -> list[Tool]:
        return [tool for tool in self._tools.values() if intent in tool.trigger_intents]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def _run(self, tool: Tool, input_obj: Any, on_event: OnEvent | None) -> Any:
        """Runs the handler under the tool's timeout, falling back — to the
        tool's declared fallback if it has one, or re-raising otherwise —
        on timeout or any handler exception. This is the one place timeout/
        fallback handling lives; a tool's handler only needs to implement
        its happy path."""
        try:
            return run_with_timeout(lambda: tool.handler(input_obj, on_event=on_event), tool.timeout_seconds)
        except Exception:
            if tool.fallback is not None:
                return tool.fallback(input_obj, on_event=on_event)
            raise

    def invoke(self, name: str, raw_input: dict, *, on_event: OnEvent | None = None) -> Any:
        """For callers with raw/untrusted input (e.g. JSON arguments) —
        validates against the tool's own schema before running it."""
        tool = self.get(name)
        parsed = tool.input_model.model_validate(raw_input)
        return self._run(tool, parsed, on_event)

    def invoke_typed(self, name: str, input_obj: Any, *, on_event: OnEvent | None = None) -> Any:
        """For callers that already hold a correctly-typed input object,
        constructed directly rather than parsed from raw JSON — skips
        schema validation. This is what the orchestrator uses: it builds
        its own typed turn-context object rather than receiving untrusted
        input."""
        tool = self.get(name)
        return self._run(tool, input_obj, on_event)


registry = ToolRegistry()
