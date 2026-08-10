"""Shared LangGraph state definition for the supervisor graph and every
specialist node (see app/modules/chatbot/agents/supervisor.py)."""

from __future__ import annotations

import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_stage: str     # prospect | applicant | admitted | student | alumni
    agent_used: str
    reply: str
    intents: List[str]  # 1-3 of: admissions | academic | financial | career |
                         # comparison | faq | assessment | general
