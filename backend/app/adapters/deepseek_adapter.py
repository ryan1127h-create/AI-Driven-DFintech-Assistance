"""
DeepSeek adapter for LLMPort. DeepSeek exposes an OpenAI-compatible Chat
Completions API, so this goes through langchain_openai.ChatOpenAI pointed
at DeepSeek's base_url rather than a DeepSeek-specific SDK — that detail
stays inside this one file; every caller only ever sees LLMPort.

A fresh ChatOpenAI instance is built per call rather than cached, since
different callers need different temperature/max_tokens combinations
(e.g. 0 for deterministic extraction vs. 0.7 for free-form chat) and the
client itself is a cheap, stateless wrapper — there's no connection or
session worth reusing across calls.
"""

from __future__ import annotations

from typing import Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.ports.llm_port import ChatMessage, LLMPort


class DeepSeekAdapter(LLMPort):
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def _build_llm(self, temperature: float, max_tokens: int) -> ChatOpenAI:
        return ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @staticmethod
    def _content_str(content) -> str:
        # .content is str for every call site in this app, but langchain's
        # type allows a list of content blocks (multi-modal responses) —
        # guard against that rather than let a non-str value silently break
        # every caller's str-only handling (JSON parsing, .strip(), ...).
        return content if isinstance(content, str) else str(content)

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        llm = self._build_llm(temperature, max_tokens)
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        return self._content_str(response.content)

    def stream(
        self,
        system_prompt: str,
        history: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        llm = self._build_llm(temperature, max_tokens)
        messages = [SystemMessage(content=system_prompt)]
        for turn in history:
            cls = HumanMessage if turn["role"] == "user" else AIMessage
            messages.append(cls(content=turn["content"]))
        for chunk in llm.stream(messages):
            if chunk.content:
                yield self._content_str(chunk.content)


llm = DeepSeekAdapter(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)
