"""Unified response envelope and escalation payload.

Implements the contract in docs/02-interface-contracts.md §1.3 and §2. Every
agent returns an AgentResponse so the (teammate-owned) dialogue module can
render results uniformly.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from .profile import LifecycleStage


class EscalationReason(str, Enum):
    """Contract §2.1, aligned with requirements doc section 11."""

    low_confidence = "low_confidence"
    policy_ambiguity = "policy_ambiguity"
    exception_case = "exception_case"
    emotionally_sensitive = "emotionally_sensitive"
    complaint_appeal = "complaint_appeal"


class EscalationRequest(BaseModel):
    """Contract §2. We generate case_id to avoid round-trips."""

    case_id: str = Field(default_factory=lambda: f"esc_{uuid.uuid4().hex[:8]}")
    source_agent: Literal["checklist", "tracker", "comparator", "navigator"]
    reason: EscalationReason
    confidence: float
    user_id: str
    lifecycle_stage: LifecycleStage
    conversation_summary: str
    structured_context: dict[str, Any] = Field(default_factory=dict)
    suggested_routing: str | None = None


class AgentResponse(BaseModel):
    """Contract §1.3 — the uniform envelope every agent returns."""

    status: Literal["ok", "need_clarification", "escalated", "error"] = "ok"
    answer_type: Literal["official", "advisory", "recommendation"] = "advisory"
    speakable: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    escalation: EscalationRequest | None = None

    @classmethod
    def needs(cls, fields: list[str], speakable: str) -> "AgentResponse":
        """Helper: return a need_clarification response for missing profile fields."""
        return cls(
            status="need_clarification",
            speakable=speakable,
            missing_fields=fields,
        )
