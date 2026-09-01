"""
Comparison presenter — the domain's only LLM step.

The repository already gathered every programme's raw facts and the match
scorer already produced the numbers. This agent only rewrites the raw text
into short, table-friendly cells, adds a one-line per-programme comment,
and writes a neutral closing summary. Code validates the output: any cell
the LLM missed falls back to the (truncated) raw text, so the endpoint
always returns a complete table.

Prompt rules: never rank programmes, keep every number exactly as given,
attribute competitor facts to that university's own published sources.
"""

from __future__ import annotations

import json

from app.adapters.deepseek_adapter import llm
from app.domains.program_comparison.models import ProgramFacts, ProgramMatch

# Raw-text fallback cell length when the LLM answer is unusable.
_FALLBACK_CELL_CHARS = 500

# The full answer is large (dimensions x programmes cells + comments +
# summary): 5000 proved too small in testing — the JSON got truncated
# mid-string.
_MAX_TOKENS = 12000

_SYSTEM_PROMPT = """\
You present a factual comparison of FinTech master's programmes for a
prospective student of the NUS MSc Digital Financial Technology (MSc DFT).

You are given each programme's raw source text per dimension, plus a
code-computed personal match score. Rewrite the raw text into compact table
cells (1-3 short sentences each — keep the total answer brief), write one
suitability comment per programme, and one closing summary.

Hard rules:
- Copy every number, fee, date, and score requirement EXACTLY as written.
  Never convert currencies, recalculate, or round.
- Never rank programmes or say one is better — present facts side by side;
  suitability comments may only relate a programme to THIS user's stated
  situation, phrased as a suggestion.
- Competitor facts come from that university's own published pages — write
  them as such (e.g. "per NTU's programme page, ..."). Never present them
  as NUS-verified.
- If a cell's raw text is empty, write exactly "No data available."
- Reply with ONLY a valid JSON object, no markdown fences:
{"cells": {"<dimension>": {"<programme>": "..."}},
 "comments": {"<programme>": "..."},
 "summary": "..."}
"""


def present(
    table: dict[str, dict[str, str]],
    programs: list[ProgramFacts],
    matches: list[ProgramMatch],
) -> tuple[dict[str, dict[str, str]], dict[str, str], str, list[str]]:
    """
    Returns (cells, comments, summary, notes). Any missing piece falls back
    to raw text (cells) or empty (comments/summary), with a note saying so.

    `table` is {dimension: {programme_name: raw_text}} — the fallback shape
    is identical, so callers never need to care which path was taken.
    """
    fallback_cells = {
        dim: {prog: (raw[:_FALLBACK_CELL_CHARS] or "No data available.")
              for prog, raw in row.items()}
        for dim, row in table.items()
    }

    match_lines = "\n".join(
        f"- {m.program}: {'no score (insufficient data)' if m.total is None else str(m.total) + '/100'}"
        for m in matches
    )
    user_prompt = (
        f"Personal match scores (already computed, for context only):\n{match_lines}\n\n"
        f"Raw facts per dimension and programme:\n{json.dumps(table, ensure_ascii=False)}"
    )

    try:
        content = llm.complete(_SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=_MAX_TOKENS)
        parsed = json.loads(content.strip())
    except Exception as exc:
        print(f"[program_comparison.comparison_agent] Warning: LLM presentation failed — {exc}")
        return fallback_cells, {}, "", [
            "Table cells show source text directly: the language model "
            "presentation step was unavailable for this request."
        ]

    cells, notes = _merge_cells(parsed, fallback_cells)
    comments = {p.name: str(parsed.get("comments", {}).get(p.name, "")).strip() for p in programs}
    summary = str(parsed.get("summary", "")).strip()
    return cells, comments, summary, notes


def _merge_cells(
    parsed: dict, fallback_cells: dict[str, dict[str, str]]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Takes the LLM's cell where present, the raw-text fallback where not."""
    llm_cells = parsed.get("cells", {})
    merged: dict[str, dict[str, str]] = {}
    missing = 0
    for dim, row in fallback_cells.items():
        merged[dim] = {}
        for prog, fallback in row.items():
            value = str(llm_cells.get(dim, {}).get(prog, "")).strip()
            if not value:
                value = fallback
                missing += 1
            merged[dim][prog] = value

    notes = []
    if missing:
        notes.append(f"{missing} table cell(s) show source text directly "
                     "(the language model skipped them).")
    return merged, notes
