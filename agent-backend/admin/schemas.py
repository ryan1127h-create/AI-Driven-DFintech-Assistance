"""Pydantic validation models for each editable data file.

These guard the authoring pipeline: an LLM-produced draft must pass validation
before it can be written. Invalid drafts are rejected, never written.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from common.profile import StatusCode


class StatusTranslationEntry(BaseModel):
    human_status: str = Field(min_length=1)
    next_step: str = Field(min_length=1)
    eta_days: int | None = Field(default=None, ge=0)  # est. days to next step


class StatusTranslations(BaseModel):
    """Schema for data/status_translations.json (the `translations` object).

    Every StatusCode must have an entry so the tracker never falls back to a
    raw code in production.
    """

    translations: dict[str, StatusTranslationEntry]

    @field_validator("translations")
    @classmethod
    def _keys_are_valid_codes(cls, v: dict) -> dict:
        valid = {s.value for s in StatusCode}
        unknown = set(v) - valid
        if unknown:
            raise ValueError(f"unknown status codes: {sorted(unknown)}")
        return v

    @model_validator(mode="after")
    def _all_codes_present(self) -> "StatusTranslations":
        valid = {s.value for s in StatusCode}
        missing = valid - set(self.translations)
        if missing:
            raise ValueError(f"missing status codes: {sorted(missing)}")
        return self


# Conditions the checklist engine can actually evaluate
# (agents/checklist/engine.py::_condition_holds). An authored rule must not
# reference anything outside this set, or the engine would be unable to evaluate
# it at runtime.
SUPPORTED_CONDITIONS = {
    "foreign_institution",
    "english_proof_required",
    "application_type",
    "degree_classification_below",
}

# How strongly an item binds the applicant. Must stay in step with
# agents/checklist/engine.py::_REQUIREMENT_LEVELS (parity-tested): a level this
# schema accepts but the engine cannot map would pass authoring and then fail at
# runtime, which is exactly what validating here is meant to prevent.
RequirementLevel = Literal["required", "conditional", "supporting"]


class DocItem(BaseModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    why: str = Field(min_length=1)
    requirement: RequirementLevel  # mandatory: the engine refuses to guess it
    deadline_key: str | None = None  # optional link to an application deadline


class ConditionalDocItem(DocItem):
    applies_when: dict[str, object] = Field(min_length=1)

    @field_validator("applies_when")
    @classmethod
    def _conditions_supported(cls, v: dict) -> dict:
        unknown = set(v) - SUPPORTED_CONDITIONS
        if unknown:
            raise ValueError(
                f"unsupported condition(s) {sorted(unknown)}; engine supports "
                f"{sorted(SUPPORTED_CONDITIONS)}"
            )
        return v


class AdmissionsRules(BaseModel):
    """Schema for data/admissions_rules.json (HIGH risk).

    Validates structure AND that conditional rules only reference conditions the
    checklist engine can evaluate — so a natural-language edit can never produce
    a rule the runtime can't handle.
    """

    base_items: list[DocItem] = Field(min_length=1)
    conditional_items: list[ConditionalDocItem] = Field(default_factory=list)
    english_exempt_countries: list[str]
    local_institution_keywords: list[str]
    # Mandatory, not defaulted: the engine falls back to "medium of instruction
    # unconfirmed" when this list is absent, so a draft that silently drops it
    # would withdraw every waiver without any visible failure.
    english_medium_institution_keywords: list[str]

    @model_validator(mode="after")
    def _keys_unique(self) -> "AdmissionsRules":
        keys = [i.key for i in self.base_items] + [i.key for i in self.conditional_items]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"duplicate item keys: {sorted(dupes)}")
        return self


class CatalogModule(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    credits: int | None = Field(default=None, ge=0)
    description: str | None = None
    source_url: str | None = None
    semesters: list[int] = Field(default_factory=list)  # offered semesters
    prereq_tree: object | None = None  # NUSMods prereqTree (str | {and/or:[...]})
    workload_hours: float | None = Field(default=None, ge=0)


class ModuleCatalog(BaseModel):
    """Schema for data/module_catalog.json (refreshed from the course catalog)."""

    source_url: str = Field(min_length=1)
    fetched_at: str = Field(min_length=1)
    modules: list[CatalogModule] = Field(min_length=1)

    @model_validator(mode="after")
    def _codes_unique(self) -> "ModuleCatalog":
        codes = [m.code for m in self.modules]
        dupes = {c for c in codes if codes.count(c) > 1}
        if dupes:
            raise ValueError(f"duplicate module codes: {sorted(dupes)}")
        return self


class CellObject(BaseModel):
    text: str = Field(min_length=1)
    kind: Literal["verified", "unknown", "synthesis"] = "verified"
    source_url: str | None = None
    fetched_at: str | None = None


class ProgramEntry(BaseModel):
    program: str = Field(min_length=1)
    is_target: bool = False
    source_url: str = Field(min_length=1)  # provenance is mandatory
    fetched_at: str = Field(min_length=1)
    values: dict[str, str | CellObject]  # bare string == verified; object == three-state
    # Legacy field: kept so older drafts validate. The engine derives role
    # strengths from curriculum_focus at runtime and never reads this.
    role_strengths: list[str] = Field(default_factory=list)


class ProgramsDataset(BaseModel):
    """Schema for data/programs_dataset.json (#6 competitor comparison).

    Every programme must cite a source_url + fetched_at, and its `values` must
    cover all declared dimensions (so comparisons aren't silently sparse).
    """

    dimensions: list[str] = Field(min_length=1)
    disclaimer: str = Field(min_length=1)
    programs: list[ProgramEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _values_cover_dimensions(self) -> "ProgramsDataset":
        for p in self.programs:
            missing = set(self.dimensions) - set(p.values)
            if missing:
                raise ValueError(f"{p.program} missing dimensions: {sorted(missing)}")
        if not any(p.is_target for p in self.programs):
            raise ValueError("no target programme (is_target) in dataset")
        return self


def validate_draft(schema: type[BaseModel], draft: dict) -> tuple[bool, str | None]:
    """Validate `draft` against `schema`. Returns (ok, error_message)."""
    try:
        schema.model_validate(draft)
        return True, None
    except Exception as e:  # pydantic ValidationError or ValueError
        return False, str(e)
