"""
Program-comparison data access — builds each programme's per-dimension raw
facts from the shared knowledge base (no new DB client, read-only).

Two data shapes are parsed:
- competitor_programs chunks (4): semi-structured text with fixed labels
  ("Fees:", "Format:", "Intake:", "Duration:", "GMAT/GRE:", "Scholarship:",
  "Curriculum focus:"). Labels are regrouped into our three dimensions.
- NUS side: there is no NUS row in competitor_programs, so NUS facts are
  assembled from the pages/rules that cover the same ground (curriculum
  rules + the page_02 Duration/Workload sections for curriculum — those two
  short sections carry the full-time/part-time duration facts that
  match_scorer.py's flexibility scoring and the competitors' own
  Format/Duration fields depend on, so leaving them out made NUS look
  part-time-blind next to every competitor that mentions it. Only these two
  sections are pulled from page_02, not the whole page: the rest overlaps
  with what the curriculum rule chunks already cover (unit breakdown) and,
  more importantly, would push Duration/Workload past
  _MAX_DIMENSION_CHARS's truncation cutoff if included first — page_06 for
  fees, page_04/05 for admission, plus the authoritative test-score FAQ
  snippet so a superseded GMAT figure is never quoted alone).
"""

from __future__ import annotations

import re

from app.modules.program_comparison.models import ProgramFacts
from app.repositories.knowledge_repository import fetch_all_chunks

NUS_PROGRAM_NAME = "NUS MSc Digital Financial Technology"

# Competitor label -> which of our dimensions its text belongs to.
_LABEL_TO_DIMENSION = {
    "Fees:": "fees",
    "Scholarship:": "fees",
    "GMAT/GRE:": "admission",
    "Intake:": "admission",
    "Curriculum focus:": "curriculum",
    "Format:": "curriculum",
    "Duration:": "curriculum",
}
_LABEL_SPLIT = re.compile(
    r"(Fees:|Scholarship:|GMAT/GRE:|Intake:|Curriculum focus:|Format:|Duration:)"
)

# NUS-side chunk selection per dimension (see module docstring).
_NUS_CURRICULUM_RULE_KEYS = ("rule:cur_degree_structure", "rule:cur_core_composition")
_NUS_CURRICULUM_PAGE = "page_02"
_NUS_CURRICULUM_SECTIONS = ("Duration of Programme", "Workload")
_NUS_FEES_PAGE = "page_06"
_NUS_ADMISSION_PAGES = ("page_04", "page_05")

# Keep each dimension's text bounded — it goes into an LLM prompt later.
_MAX_DIMENSION_CHARS = 4000

_competitors_cache: list[ProgramFacts] | None = None
_nus_cache: ProgramFacts | None = None


def _parse_competitor(chunk: dict) -> ProgramFacts:
    """Splits one competitor chunk's labelled text into dimension buckets."""
    name = chunk["chunk_key"].split(":", 1)[1]
    parts = _LABEL_SPLIT.split(chunk["content"])

    buckets: dict[str, list[str]] = {}
    for label, body in zip(parts[1::2], parts[2::2], strict=True):
        dimension = _LABEL_TO_DIMENSION[label]
        buckets.setdefault(dimension, []).append(f"{label} {body.strip()}")

    md = chunk["metadata"] or {}
    return ProgramFacts(
        name=name,
        is_nus=False,
        dimension_text={
            dim: "\n".join(lines)[:_MAX_DIMENSION_CHARS] for dim, lines in buckets.items()
        },
        source_urls=(md["source_url"],) if md.get("source_url") else (),
    )


def load_competitors() -> list[ProgramFacts]:
    global _competitors_cache
    if _competitors_cache is None:
        _competitors_cache = [
            _parse_competitor(c)
            for c in fetch_all_chunks()
            if c["source_table"] == "competitor_programs"
        ]
    return _competitors_cache


def load_nus() -> ProgramFacts:
    """Assembles the NUS row from curriculum rules + fees/admission pages."""
    global _nus_cache
    if _nus_cache is not None:
        return _nus_cache

    curriculum: list[str] = []
    fees: list[str] = []
    admission: list[str] = []
    urls: list[str] = []

    for chunk in fetch_all_chunks():
        md = chunk["metadata"] or {}
        text = f"{chunk['context']}\n{chunk['content']}" if chunk["context"] else chunk["content"]

        if chunk["chunk_key"] in _NUS_CURRICULUM_RULE_KEYS:
            curriculum.append(chunk["content"])
        elif md.get("page_id") == _NUS_CURRICULUM_PAGE and md.get("section_title") in _NUS_CURRICULUM_SECTIONS:
            curriculum.append(text)
        elif md.get("page_id") == _NUS_FEES_PAGE:
            fees.append(text)
        elif md.get("page_id") in _NUS_ADMISSION_PAGES:
            admission.append(text)
        elif chunk["conflict_group"] and chunk["authoritative"]:
            # The FAQ entry that governs test-score policy — appended so the
            # LLM never quotes a superseded figure as current.
            admission.append(f"OFFICIAL FAQ (governs where figures disagree): {chunk['content']}")
        else:
            continue

        url = md.get("source_url")
        if url and url not in urls:
            urls.append(url)

    _nus_cache = ProgramFacts(
        name=NUS_PROGRAM_NAME,
        is_nus=True,
        dimension_text={
            "curriculum": "\n\n".join(curriculum)[:_MAX_DIMENSION_CHARS],
            "fees": "\n\n".join(fees)[:_MAX_DIMENSION_CHARS],
            "admission": "\n\n".join(admission)[:_MAX_DIMENSION_CHARS],
        },
        source_urls=tuple(urls),
    )
    return _nus_cache
