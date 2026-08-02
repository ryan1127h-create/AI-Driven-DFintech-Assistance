"""Retrieval confidence gate for official-source question answering.

This module is deliberately lightweight and stdlib-only. In production the RAG
team should pass calibrated embedding scores. For MVP/testing we can also fall
back to a simple lexical overlap score when chunks do not contain a score.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from common.envelope import AgentResponse, EscalationReason, EscalationRequest
from common.profile import UserProfile

LOW_CONFIDENCE_THRESHOLD = 0.60
CLARIFICATION_THRESHOLD = 0.72
STRICT_OFFICIAL_THRESHOLD = 0.80

_THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "data" / "thresholds.json"


@lru_cache(maxsize=8)
def _load_thresholds(backend: str = "bm25") -> dict[str, float]:
    """Calibrated thresholds for a retrieval backend, else built-in defaults.

    data/thresholds.json is keyed per backend, e.g.
        {"bm25": {...}, "embedding": {...}}
    Different backends produce different score distributions, so each carries its
    own thresholds. A legacy flat {low,clarification,strict} file applies to any
    backend. Unknown backend or missing file -> built-in constants.
    """
    defaults = {
        "low": LOW_CONFIDENCE_THRESHOLD,
        "clarification": CLARIFICATION_THRESHOLD,
        "strict": STRICT_OFFICIAL_THRESHOLD,
    }
    try:
        import json
        data = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        section = data.get(backend)
        if not isinstance(section, dict):
            # Legacy flat file: top-level low/clarification/strict.
            section = data if "low" in data else {}
        return {k: float(section.get(k, defaults[k])) for k in defaults}
    except (OSError, ValueError):
        return defaults


# Matched as substrings (`k in text`), so a phrase whose shorter form is also
# listed would never add a match: "deadline extension" is covered by "extension".
_HIGH_RISK_KEYWORDS = (
    "appeal", "complaint", "exception", "waiver", "extension",
    "missed deadline", "late application", "special case", "case by case",
    "special circumstance",
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class RetrievalChunk:
    text: str
    source_id: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class ConfidenceDecision:
    action: str  # answer | clarify | escalate
    confidence: float
    reason: EscalationReason | None = None
    message: str = ""
    sources: list[str] | None = None


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _lexical_similarity(query: str, text: str) -> float:
    """Cosine on term frequencies; intended only as an offline fallback."""
    qt = _tokens(query)
    tt = _tokens(text)
    if not qt or not tt:
        return 0.0

    def counts(xs: Iterable[str]) -> dict[str, int]:
        d: dict[str, int] = {}
        for x in xs:
            d[x] = d.get(x, 0) + 1
        return d

    qd, td = counts(qt), counts(tt)
    common = set(qd) & set(td)
    dot = sum(qd[k] * td[k] for k in common)
    qn = math.sqrt(sum(v * v for v in qd.values()))
    tn = math.sqrt(sum(v * v for v in td.values()))
    return round(dot / (qn * tn), 4) if qn and tn else 0.0


def _as_chunk(raw: Any, query: str) -> RetrievalChunk:
    if isinstance(raw, RetrievalChunk):
        return raw
    if isinstance(raw, dict):
        text = str(raw.get("text") or raw.get("content") or "")
        sid = raw.get("source_id") or raw.get("source")
        score = raw.get("score")
        try:
            score_f = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_f = None
        return RetrievalChunk(
            text=text,
            source_id=str(sid) if sid else None,
            score=score_f if score_f is not None else _lexical_similarity(query, text),
        )
    text = str(raw or "")
    return RetrievalChunk(text=text, score=_lexical_similarity(query, text))


def _top_score_and_sources(query: str, chunks: list[Any]) -> tuple[float, list[str]]:
    parsed = [_as_chunk(c, query) for c in chunks]
    if not parsed:
        return 0.0, []
    parsed = sorted(parsed, key=lambda c: c.score or 0.0, reverse=True)
    sources = [c.source_id for c in parsed if c.source_id]
    return float(parsed[0].score or 0.0), list(dict.fromkeys(sources))


def looks_high_risk(query: str, *, answer_type: str = "advisory") -> bool:
    text = (query or "").lower()
    return answer_type == "official" or any(k in text for k in _HIGH_RISK_KEYWORDS)


def decide(
    query: str,
    chunks: list[Any],
    *,
    answer_type: str = "advisory",
    high_risk: bool = False,
    low_threshold: float | None = None,
    clarification_threshold: float | None = None,
    strict_threshold: float | None = None,
    backend: str = "bm25",
) -> ConfidenceDecision:
    """Decide whether to answer, clarify, or escalate after RAG retrieval.

    `backend` selects which calibrated threshold set to use when thresholds are
    not passed explicitly (the active retriever's distribution differs by backend).
    """
    t = _load_thresholds(backend)
    if low_threshold is None:
        low_threshold = t["low"]
    if clarification_threshold is None:
        clarification_threshold = t["clarification"]
    if strict_threshold is None:
        strict_threshold = t["strict"]
    top, sources = _top_score_and_sources(query, chunks)
    risky = high_risk or looks_high_risk(query, answer_type=answer_type)

    if not chunks:
        return ConfidenceDecision(
            action="escalate",
            confidence=0.0,
            reason=EscalationReason.low_confidence,
            message="Not enough relevant official material was found; human confirmation is recommended.",
            sources=[],
        )
    if top < low_threshold:
        return ConfidenceDecision(
            action="escalate",
            confidence=top,
            reason=EscalationReason.low_confidence,
            message="The retrieved official material has low similarity to the question, so an answer should not be generated directly.",
            sources=sources,
        )
    if risky and top < strict_threshold:
        return ConfidenceDecision(
            action="escalate",
            confidence=top,
            reason=EscalationReason.policy_ambiguity,
            message="This question involves official policy or an exception case and requires higher confidence or human confirmation.",
            sources=sources,
        )
    if top < clarification_threshold:
        return ConfidenceDecision(
            action="clarify",
            confidence=top,
            message="Some relevant material was found, but similarity is insufficient for a direct answer; clarification is needed first.",
            sources=sources,
        )
    return ConfidenceDecision(action="answer", confidence=top, sources=sources)


def response_from_decision(
    decision: ConfidenceDecision,
    *,
    profile: UserProfile,
    source_agent: str,
    query: str,
    suggested_routing: str = "programme_office",
) -> AgentResponse | None:
    """Convert a non-answer decision into the standard AgentResponse envelope."""
    if decision.action == "answer":
        return None
    data = {
        "confidence": decision.confidence,
        "confidence_action": decision.action,
        "reason": decision.reason.value if decision.reason else None,
        "sources": decision.sources or [],
    }
    if decision.action == "clarify":
        return AgentResponse(
            status="need_clarification",
            answer_type="advisory",
            speakable="I found some relevant official material, but it is not certain enough yet. Please add your specific question or current stage, and I will help you assess it.",
            data=data,
            sources=decision.sources or [],
            missing_fields=["query_clarification"],
        )

    esc = EscalationRequest(
        source_agent=source_agent,  # type: ignore[arg-type]
        reason=decision.reason or EscalationReason.low_confidence,
        confidence=decision.confidence,
        user_id=profile.user_id,
        lifecycle_stage=profile.lifecycle_stage,
        conversation_summary=f"User question could not be answered safely from official sources: {query}",
        structured_context={
            "user_question": query,
            "top_similarity": decision.confidence,
            "retrieved_sources": decision.sources or [],
            "gate_message": decision.message,
        },
        suggested_routing=suggested_routing,
    )
    return AgentResponse(
        status="escalated",
        answer_type="official",
        speakable="This question did not match sufficiently reliable official material, or it involves policy interpretation or an exception case. I have prepared it for human handling.",
        data=data,
        sources=decision.sources or [],
        escalation=esc,
    )
