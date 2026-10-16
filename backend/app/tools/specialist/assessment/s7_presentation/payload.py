"""
S7 — turns the domain's assessment into the render view the reply is
written from: the verdict, the hard conditions, the competitiveness
(strengths and the two improvements worth making), the application
period, what is still unknown, the notes, and the official sources.
Profile values in the findings are shown as the profile names them.
"""

from __future__ import annotations

import re

from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched
from app.tools.specialist.assessment.s7_presentation.missing_info import PROMPTS

HARD_LABELS = {
    "degree": "Degree background",
    "programming_or_quant": "Programming or quantitative preparation",
    "english": "English proficiency",
    "timing": "Application period",
}
HARD_STATUS = {"met": "met", "exempt": "not needed", "to_confirm": "to confirm", "gap": "gap"}
SOFT_LABELS = {
    "background_fit": "Degree background fit",
    "programming_depth": "Programming depth",
    "quant_foundation": "Quantitative foundation",
    "finance_foundation": "Finance foundation",
    "relevant_experience": "Relevant experience",
    "academic_record": "Academic record",
    "test_scores": "GMAT / GRE",
}
VERDICTS = {
    "all_met": "Every hard condition is met.",
    "to_confirm": "No hard condition is failing, but some still need confirming.",
    "gap": "At least one hard condition isn't met yet.",
}
DISCLAIMER = ("This is a readiness check against the programme's published requirements — not an admission "
              "decision or a prediction of one.")
_SOURCE_NAMES = {"cv": "your CV", "profile": "your profile", "message": "your message"}
_VALUE_PART = re.compile(r"^(discipline|experience|coursework|certification|GPA band|tech stack): (.+)$")


def _labelled(finding: str, labels: dict) -> str:
    """'discipline: cs_se; coursework: dsa' -> the profile's names for the
    values, only inside such 'label: value' parts."""
    def name(value: str) -> str:
        raw, _, note = value.strip().partition(" (")  # "cs_se (computing)"
        return labels.get(raw, raw) + (f" ({note}" if note else "")

    parts = []
    for part in finding.split("; "):
        match = _VALUE_PART.match(part)
        if match:
            part = f"{match.group(1)}: {', '.join(name(v) for v in match.group(2).split(', '))}"
        parts.append(part)
    return "; ".join(parts)


def _facts_from(sources: dict) -> str | None:
    """Where the facts used came from, in words: "your CV, your message"."""
    kinds = [name for kind, name in _SOURCE_NAMES.items() if kind in set(sources.values())]
    return ", ".join(kinds) or None


def to_render_view(result: dict, prefetched: Prefetched, notes: list[str] | tuple[str, ...] = ()) -> dict:
    labels = prefetched.value_labels
    soft = {s["key"]: s for s in result["soft"]}
    window = None
    if result["application_closes"]:
        opens = f"{result['application_opens']} to " if result["application_opens"] else "until "
        window = f"August {result['intake_year']} intake: {opens}{result['application_closes']}"
    sources = [c["source_url"] for c in result["hard"]] + [s["source_url"] for s in result["soft"]]
    return {
        "mode": "assessment",
        "verdict": {"status": result["verdict"], "summary": VERDICTS[result["verdict"]]},
        "based_on": _facts_from(result["fact_sources"]),
        "applicant_type": result["applicant_type"],
        "hard_conditions": [
            {"condition": HARD_LABELS[c["key"]], "status": HARD_STATUS[c["status"]], "requirement": c["requirement"],
             "finding": _labelled(c["finding"], labels), "action": c["action"]}
            for c in result["hard"]
        ],
        "strengths": [
            {"factor": SOFT_LABELS[k], "finding": _labelled(soft[k]["finding"], labels), "basis": soft[k]["basis"]}
            for k in result["strengths"]
        ],
        # Every improvement is a suggestion; "optional" marks the ones the
        # programme doesn't ask for at all (GMAT/GRE) — left out otherwise,
        # so a reply doesn't read its absence as "required".
        "worth_strengthening": [
            {"factor": SOFT_LABELS[k], "finding": _labelled(soft[k]["finding"], labels), "basis": soft[k]["basis"],
             "action": soft[k]["action"], **({"optional": True} if soft[k]["optional"] else {})}
            for k in result["improvements"]
        ],
        "application_period": window,
        "still_unknown": [PROMPTS.get(f, f) for f in result["missing_fields"]],
        "notes": list(notes),
        "disclaimer": DISCLAIMER,
        "sources": list(dict.fromkeys(u for u in sources if u)),
    }
