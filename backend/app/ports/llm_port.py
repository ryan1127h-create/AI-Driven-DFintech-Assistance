"""
Contract for "send prompts to a chat-completion model, get text back".
Callers depend on this shape, not on any specific provider's SDK, so the
model/provider behind it can be swapped by writing a new adapter, with no
change to any calling domain.

`ChatMessage` is a plain, provider-agnostic role/content pair — deliberately
not a specific SDK's message type, so no framework type crosses this
boundary in either direction.
"""

from __future__ import annotations

from typing import Iterator, Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str  # "user" or "assistant"
    content: str


class LLMPort(Protocol):
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Returns the model's response text for one system+user turn — no
        conversation history, no tool calls, no streaming."""
        ...

    def stream(
        self,
        system_prompt: str,
        history: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        """Streams response text chunks for a system prompt plus a full
        conversation history (oldest first; the last entry is the newest
        user turn)."""
        ...
