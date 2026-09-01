"""Exercises the paths a Tool call can take: success, timeout-with-fallback,
failure-with-no-fallback, and looking up a name nothing registered — via
both invoke() (raw/JSON input) and invoke_typed() (pre-built input)."""

from __future__ import annotations

import time

import pytest
from pydantic import BaseModel

from app.tools.contracts import Tool, ToolNotFoundError, ToolRegistry


class EchoInput(BaseModel):
    message: str


def test_invoke_returns_handler_result():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo", description="Echoes its input.", input_model=EchoInput,
            handler=lambda inp, on_event=None: inp.message,
        )
    )
    assert registry.invoke("echo", {"message": "hi"}) == "hi"


def test_invoke_typed_skips_validation():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo", description="Echoes its input.", input_model=EchoInput,
            handler=lambda inp, on_event=None: inp.message,
        )
    )
    assert registry.invoke_typed("echo", EchoInput(message="hi")) == "hi"


def test_invoke_passes_on_event_through():
    registry = ToolRegistry()
    events: list[dict] = []
    registry.register(
        Tool(
            name="notify", description="Emits one event.", input_model=EchoInput,
            handler=lambda inp, on_event=None: on_event({"type": "token", "text": inp.message}),
        )
    )
    registry.invoke("notify", {"message": "hi"}, on_event=events.append)
    assert events == [{"type": "token", "text": "hi"}]


def test_invoke_falls_back_on_timeout():
    registry = ToolRegistry()

    def _slow(inp: EchoInput, on_event=None) -> str:
        time.sleep(1)
        return inp.message

    registry.register(
        Tool(
            name="slow_echo",
            description="Sleeps past its own timeout.",
            input_model=EchoInput,
            handler=_slow,
            timeout_seconds=0.05,
            fallback=lambda inp, on_event=None: "fallback",
        )
    )
    assert registry.invoke("slow_echo", {"message": "hi"}) == "fallback"


def test_invoke_reraises_when_no_fallback():
    registry = ToolRegistry()

    def _broken(inp: EchoInput, on_event=None) -> str:
        raise RuntimeError("boom")

    registry.register(
        Tool(name="broken", description="Always raises.", input_model=EchoInput, handler=_broken)
    )
    with pytest.raises(RuntimeError):
        registry.invoke("broken", {"message": "hi"})


def test_unregistered_tool_raises_tool_not_found():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.invoke("nope", {"message": "hi"})


def test_duplicate_registration_rejected():
    registry = ToolRegistry()
    tool = Tool(name="dup", description="d", input_model=EchoInput, handler=lambda inp, on_event=None: inp.message)
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.register(tool)
