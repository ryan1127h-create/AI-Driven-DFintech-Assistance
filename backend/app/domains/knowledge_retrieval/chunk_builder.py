"""
Rebuilds the retrieval chunk of one structured knowledge row — an admission
requirement, an application status, a course or a curriculum rule — in the
exact shape the existing chunks in knowledge.document_chunks were built
with, so the staff console can refresh a chunk after editing its row.

Pure functions: the caller loads the rows and stores the result. The web
page chunks are built elsewhere (scripts/knowledge/rebuild_web_chunks.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PROGRAMME = "the NUS MSc Digital Financial Technology (MSc DFinTech)"


@dataclass(frozen=True)
class BuiltChunk:
    chunk_key: str
    source_table: str
    source_id: str
    content: str
    context: str
    metadata: dict

    @property
    def token_count(self) -> int:
        # The stored chunks count whitespace-separated words of context and
        # content, not tokenizer tokens.
        return len(f"{self.context} {self.content}".split())

    @property
    def embedding_text(self) -> str:
        """What the retriever's vectors are computed from."""
        return f"{self.context}\n{self.content}"


def _units(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return format(value, "g") if isinstance(value, float) else str(value)


def admission_item(row: dict) -> BuiltChunk:
    """row: knowledge.admissions_items (key, label, why, required, deadline_key)."""
    label = row["label"]
    return BuiltChunk(
        chunk_key=f"admission:{row['key']}",
        source_table="admissions_items",
        source_id=row["key"],
        content=f"{label} — {'Required' if row['required'] else 'Optional or conditional'}. {row['why']}",
        context=f'Application document requirement for {PROGRAMME}: "{label}". '
                "Useful for the application checklist and what to submit.",
        metadata={"required": bool(row["required"]), "deadline_key": row.get("deadline_key")},
    )


def application_status(row: dict) -> BuiltChunk:
    """row: knowledge.application_status_translations (status_code,
    human_status, next_step, eta_days)."""
    code, eta = row["status_code"], row.get("eta_days")
    content = f'Application status "{row["human_status"].strip()}". Next step: {row["next_step"].strip()}'
    if eta:
        content += f" (typically about {eta} days)."
    metadata = {"status_code": code}
    if eta:
        metadata = {"eta_days": eta, **metadata}
    return BuiltChunk(
        chunk_key=f"status:{code}",
        source_table="application_status_translations",
        source_id=code,
        content=content,
        context=f"NUS MSc DFinTech application status explanation for {code}. "
                "Useful for application tracking and understanding what a status means.",
        metadata=metadata,
    )


def course(row: dict, tags: list[dict], previous_metadata: dict | None) -> BuiltChunk:
    """row: knowledge.courses joined with course_descriptions and
    course_requirements (course_code, title, module_credit, department,
    annex_section, annex_intake, status, description, prerequisite,
    preclusion). tags: [{tag, name_zh}]. previous_metadata: the existing
    chunk's metadata — faculty, source_url and can_recommend live only
    there, so they are carried over."""
    code, title, units = row["course_code"], row["title"], _units(row.get("module_credit"))
    metadata = dict(previous_metadata or {})
    for key in ("status", "department", "annex_intake", "annex_section"):
        # An empty field is left out rather than stored as null.
        if row.get(key) is None:
            metadata.pop(key, None)
        else:
            metadata[key] = row[key]
    faculty = ", ".join(part for part in (metadata.get("faculty"), row.get("department")) if part)
    content = f"{code} {title} ({units} units)."
    if faculty:
        content += f" Faculty: {faculty}."
    if row.get("description"):
        content += f" Description: {row['description']}"
    if row.get("prerequisite"):
        content += f" Prerequisite: {row['prerequisite']}"
    if row.get("preclusion"):
        content += f" Preclusion: {row['preclusion']}"
    if tags:
        content += " Topic tags: " + "; ".join(
            f"{t['tag']} ({t['name_zh']})" for t in sorted(tags, key=lambda t: t["tag"])
        ) + "."
    return BuiltChunk(
        chunk_key=f"course:{code}",
        source_table="courses",
        source_id=code,
        content=content,
        context=f'This describes course {code} "{title}", a {units}-unit course relevant to {PROGRAMME}. '
                "Useful for questions about this course's content, prerequisites, topic area, and course recommendation.",
        metadata=metadata,
    )


def course_rule(row: dict) -> BuiltChunk:
    """row: knowledge.course_rules (id, intake, category, text)."""
    return BuiltChunk(
        chunk_key=f"rule:{row['id']}",
        source_table="course_rules",
        source_id=row["id"],
        content=row["text"],
        context=f"Curriculum rule ({row['category']}) for {PROGRAMME}, applicable to the {row['intake']} intake.",
        metadata={"intake": row["intake"], "category": row["category"]},
    )
