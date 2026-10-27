"""
Profile certifications as career-planning evidence. The profile stores
each one as {key, level} (field_definitions.certifications: "only
certifications already obtained"), the level in free text — "L2",
"Charterholder", "Part 1", "AWS Solutions Architect".

A CFA with a level other than the charter, or an FRM with only Part 1,
means exams passed so far, not the credential: it becomes "<key>_partial",
which the skill rules count as moderate evidence instead of strong
(policy/skill_evidence.py). The reply shows the level either way, so a
CFA Level II candidate is never described as holding the CFA.
"""

from __future__ import annotations

import re

PARTIAL_SUFFIX = "_partial"
_FRM_PART_1 = re.compile(r"\bpart\s*(?:1|i)\b")
_FRM_PART_2 = re.compile(r"\bpart\s*(?:2|ii)\b")


def _is_partial(key: str, level: str) -> bool:
    level = level.lower()
    if key == "cfa":
        return "charter" not in level
    if key == "frm":
        return bool(_FRM_PART_1.search(level)) and not _FRM_PART_2.search(level)
    return False


def evidence_key(item) -> str | None:
    """The key the skill rules match: "cfa", or "cfa_partial" for exams
    passed without the charter."""
    if not isinstance(item, dict):
        return item
    key, level = item.get("key"), str(item.get("level") or "").strip()
    if key and level and _is_partial(key, level):
        return key + PARTIAL_SUFFIX
    return key


def evidence_label(item, key_label: str) -> str:
    """How the certification reads in the reply: its label, with the level
    and, for exams in progress, that the credential isn't held yet."""
    level = str(item.get("level") or "").strip() if isinstance(item, dict) else ""
    if not level:
        return key_label
    if evidence_key(item).endswith(PARTIAL_SUFFIX):
        return f"{key_label} ({level} passed — exams in progress, credential not yet held)"
    return f"{key_label} ({level})"
