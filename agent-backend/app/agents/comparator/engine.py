"""#6 Comparator engine v2.

- Derives each programme's role strengths from its curriculum_focus text via an
  explainable keyword rubric (no hand-assigned strengths).
- Scores programmes on deterministic criteria (role_fit / cost / duration) and
  combines them with user-supplied priority weights.

This is a personalised *fit* signal, NOT a quality ranking of programmes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from common.profile import TargetRole

_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "programs_dataset.json"

# HKD -> SGD approximate rate (for rough cost comparability only).
_HKD_TO_SGD = 0.17

# Role -> curriculum-evidence keywords, case-insensitive. English only: the
# dataset is English, so zh keywords were unreachable dead weight.
#
# A keyword must name CURRICULUM CONTENT that can tell programmes apart. Two
# kinds of keyword are deliberately absent, and re-adding them is a regression:
#   - domain/title terms ("fintech", "financial technology"): every programme in
#     the comparison set carries FinTech in its own name, so matching one
#     restates the title instead of evidencing curriculum fit.
#   - adjacent-but-different topics ("risk management" for compliance_regtech):
#     the score would be real but justified with text about something else.
# When the dataset holds no evidence for a role, it scores a truthful zero.
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "fintech_pm": ["product", "venture", "entrepreneurship", "insight"],
    "quant_risk": ["risk", "quantitative", "modelling", "modeling",
                   "financial engineering"],
    "digital_banking": ["bank", "banking", "digital finance",
                        "digital financial services"],
    "payments": ["payment", "blockchain", "transaction"],
    "compliance_regtech": ["compliance", "regulation", "regulatory", "regtech",
                           "anti-money laundering"],
    "data_analytics": ["data", "analysis", "analytics", "machine learning",
                       "data science", "intelligence", "ai"],
}

# Multi-word keywords are joined by this class so matching tolerates either
# separator. The table itself mixes both -- "machine learning" is spaced while
# "anti-money laundering" is hyphenated -- and matching must not depend on which
# separator a future dataset refresh happens to use.
_KEYWORD_SEPARATOR = r"[\s\-]+"

_CRITERIA = ("role_fit", "cost", "duration")

# Cell provenance kinds (spec §2.1). verified -> sourced fact; unknown -> not
# published; synthesis -> editorial/AI interpretation (never scored).
_VERIFIED, _UNKNOWN, _SYNTHESIS = "verified", "unknown", "synthesis"
_CELL_KINDS = {_VERIFIED, _UNKNOWN, _SYNTHESIS}


@dataclass(frozen=True)
class FactCell:
    text: str
    kind: str  # verified | unknown | synthesis
    source_url: str | None = None
    fetched_at: str | None = None


def _normalize_cell(raw, row_src: str | None, row_fetched: str | None) -> FactCell:
    """Normalize a raw cell (bare string OR object) into a FactCell.

    Bare string -> verified, inheriting the row-level source. An object's source
    is inherited only for verified cells (unknown/synthesis carry no provenance).
    """
    if isinstance(raw, dict):
        kind = raw.get("kind", _VERIFIED)
        if kind not in _CELL_KINDS:
            kind = _VERIFIED
        verified = kind == _VERIFIED
        return FactCell(
            text=str(raw.get("text", "")),
            kind=kind,
            source_url=raw.get("source_url", row_src if verified else None),
            fetched_at=raw.get("fetched_at", row_fetched if verified else None),
        )
    return FactCell(text=str(raw), kind=_VERIFIED, source_url=row_src, fetched_at=row_fetched)


def _row_facts(p: dict) -> dict[str, FactCell]:
    src, fetched = p.get("source_url"), p.get("fetched_at")
    return {dim: _normalize_cell(raw, src, fetched) for dim, raw in p.get("values", {}).items()}


def _verified_text(facts: dict[str, FactCell], dim: str) -> str | None:
    cell = facts.get(dim)
    return cell.text if (cell is not None and cell.kind == _VERIFIED) else None


# Cross-programme ranking phrases the narrative must never produce (spec §4).
# Deliberately conservative: a false positive only forces the safe fallback.
# "best fit / 最适合你 / 更契合 / 更好地<动词>" are fit-to-goal phrasing, NOT banned
# (so 更好 is only flagged when it is NOT the adverbial 更好地). Noun heads allow an
# optional plural 's' so "best programmes", "top programs" etc. are still caught.
_RANKING_PATTERNS = [
    r"优于", r"更好(?!地)", r"胜过", r"排名", r"第一名", r"最好的(?:项目|选择|课程|学校)",
    r"\bbetter than\b", r"\bbest (?:program|programme|option|choice|school)s?\b",
    r"\boutperform", r"\bsuperior to\b", r"#1\b", r"\branked\b",
    r"\btop (?:program|programme)s?\b",
]


def violates_ranking(text: str) -> bool:
    """True if `text` contains a cross-programme ranking claim."""
    t = (text or "").lower()
    return any(re.search(p, t) for p in _RANKING_PATTERNS)


def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


# ---------- role derivation (explainable) ----------
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Word-boundary regex for one keyword.

    A keyword must not match inside a longer word: bare containment let "ai" hit
    "blockchain"/"training" and inflate role_reasons. An optional trailing "s"
    keeps plurals ("transactions") matching, and multi-word keywords tolerate
    either separator ("anti-money laundering" / "anti money laundering").
    """
    parts = [re.escape(part) for part in re.split(_KEYWORD_SEPARATOR, keyword.lower()) if part]
    body = _KEYWORD_SEPARATOR.join(parts)
    return re.compile(rf"\b{body}s?\b")


_KEYWORD_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    role: [(kw, _keyword_pattern(kw)) for kw in kws]
    for role, kws in _ROLE_KEYWORDS.items()
}


def _keyword_hits(text: str, role: str) -> list[str]:
    """Keywords of `role` present in `text` (already lower-cased)."""
    return [kw for kw, pattern in _KEYWORD_PATTERNS[role] if pattern.search(text)]


def derive_role_strengths(curriculum_focus: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return (roles, reasons) where reasons[role] = matched keywords."""
    text = (curriculum_focus or "").lower()
    roles: list[str] = []
    reasons: dict[str, list[str]] = {}
    for role in _ROLE_KEYWORDS:
        hits = _keyword_hits(text, role)
        if hits:
            roles.append(role)
            reasons[role] = hits
    return roles, reasons


# ---------- deterministic scoring helpers ----------
def parse_fee_sgd(fees_text: str) -> float | None:
    """Extract an approximate SGD fee magnitude from a free-text fees field."""
    m = re.search(r"(HK\$|HKD|S\$|SGD)\s?([\d,]+)", fees_text or "", re.IGNORECASE)
    if not m:
        return None
    amount = float(m.group(2).replace(",", ""))
    cur = m.group(1).upper()
    if cur in ("HK$", "HKD"):
        amount *= _HKD_TO_SGD
    return amount


def parse_min_months(duration_text: str) -> int | None:
    """Smallest plausible duration in months from a free-text duration field.

    Supports Chinese and English phrases such as "18 个月", "1.5 years",
    "12 to 24 months", and "1 year full-time; 2 years part-time".
    """
    text = duration_text or ""
    months: list[int] = []
    # English ranges: 12 to 24 months / 1-2 years -> lower bound.
    for a, _b, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(months?|years?)", text, re.IGNORECASE):
        val = float(a)
        months.append(round(val * 12) if unit.lower().startswith("year") else round(val))
    # Chinese ranges: 1-2 年.
    for a, _b in re.findall(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*年", text):
        months.append(round(float(a) * 12))
    # Standalone English years/months.
    for y in re.findall(r"(?<![-\d.])(\d+(?:\.\d+)?)\s*years?", text, re.IGNORECASE):
        months.append(round(float(y) * 12))
    for mth in re.findall(r"(?<![-\d.])(\d+(?:\.\d+)?)\s*months?", text, re.IGNORECASE):
        months.append(round(float(mth)))
    # Standalone Chinese years/months.
    for y in re.findall(r"(?<![-\d.])(\d+(?:\.\d+)?)\s*年", text):
        months.append(round(float(y) * 12))
    for mth in re.findall(r"(\d+(?:\.\d+)?)\s*个月", text):
        months.append(round(float(mth)))
    return min(months) if months else None


def _inverse_minmax(values: dict[str, float | None]) -> dict[str, float]:
    """Lower raw value -> higher score (0..1). Unknown (None) -> neutral 0.5."""
    known = [v for v in values.values() if v is not None]
    out = {k: 0.5 for k in values}
    if len(known) < 2:
        return out  # not enough spread to rank; all neutral
    lo, hi = min(known), max(known)
    if hi == lo:
        return out
    for k, v in values.items():
        if v is not None:
            out[k] = (hi - v) / (hi - lo)
    return out


def _normalise_weights(priorities: dict[str, float] | None) -> dict[str, float]:
    p = {k: float(v) for k, v in (priorities or {}).items()
         if k in _CRITERIA and float(v) > 0}
    if not p:
        p = {"role_fit": 1.0}
    total = sum(p.values())
    return {k: v / total for k, v in p.items()}


# ---------- comparison ----------
@dataclass
class RowSynthesis:
    matched_roles: list[str]
    role_reasons: dict[str, list[str]]
    weighted_score: float
    score_breakdown: dict[str, float]


@dataclass
class ComparisonRow:
    program: str
    is_target: bool
    facts: dict[str, FactCell]
    synthesis: RowSynthesis
    source_url: str | None = None   # row-level default provenance
    fetched_at: str | None = None


@dataclass
class Comparison:
    dimensions: list[str]
    rows: list[ComparisonRow]
    disclaimer: str
    best_for_you: str | None
    weights: dict[str, float] = field(default_factory=dict)


def compare(target_roles: list[TargetRole],
            priorities: dict[str, float] | None = None) -> Comparison:
    data = _load()
    role_values = {r.value for r in target_roles}
    weights = _normalise_weights(priorities)
    progs = data["programs"]
    facts_by_prog = {p["program"]: _row_facts(p) for p in progs}

    # Per-criterion raw values come from VERIFIED cells only; unknown/synthesis
    # -> None -> neutral 0.5 (via _inverse_minmax). Subjective cells never scored.
    fee_raw = {p["program"]: parse_fee_sgd(_verified_text(facts_by_prog[p["program"]], "fees") or "")
               for p in progs}
    dur_raw = {p["program"]: parse_min_months(_verified_text(facts_by_prog[p["program"]], "duration") or "")
               for p in progs}
    cost_score = _inverse_minmax(fee_raw)
    dur_score = _inverse_minmax(dur_raw)

    rows: list[ComparisonRow] = []
    for p in progs:
        name = p["program"]
        facts = facts_by_prog[name]
        roles, reasons = derive_role_strengths(_verified_text(facts, "curriculum_focus") or "")
        matched = sorted(role_values & set(roles))
        role_fit = (len(matched) / len(role_values)) if role_values else 0.0
        breakdown = {
            "role_fit": role_fit,
            "cost": cost_score[name],
            "duration": dur_score[name],
        }
        weighted = sum(weights[k] * breakdown[k] for k in weights)
        rows.append(ComparisonRow(
            program=name, is_target=p.get("is_target", False),
            facts=facts,
            synthesis=RowSynthesis(
                matched_roles=matched,
                role_reasons={r: reasons[r] for r in matched},
                weighted_score=round(weighted, 4),
                score_breakdown=breakdown,
            ),
            source_url=p.get("source_url"), fetched_at=p.get("fetched_at"),
        ))

    best = None
    if rows:
        # is_target breaks a score tie in favour of the target programme.
        best_row = max(rows, key=lambda r: (r.synthesis.weighted_score, r.is_target))
        # A zero top score means nothing in the verified data supports a
        # recommendation; emit none rather than an evidence-free "best fit".
        if best_row.synthesis.weighted_score > 0:
            best = best_row.program

    return Comparison(
        dimensions=data["dimensions"], rows=rows, disclaimer=data["disclaimer"],
        best_for_you=best, weights=weights,
    )
