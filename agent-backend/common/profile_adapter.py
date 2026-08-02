"""Explicit two-way adapter between the rag-data profile shape and the authority model.

The retrieval side (`rag-data/`, owned by a teammate, read-only for us) stores
profiles in the nested `{raw, std}` shape documented in
`rag-data/docs/user_profile_schema.md`. The one authoritative profile in this
backend is `common.profile.UserProfile`. This module is the only place where the
two vocabularies are allowed to meet.

Three rules the whole module obeys:

1. **Loud, never silent.** A value with no defined mapping raises
   `ProfileMappingError` naming the field and the received value. There is no
   `or default`, no `except: pass`, no `.get(key, something_plausible)`. An
   unrecognised stage word quietly becoming "currently enrolled" is what would
   hand an alumnus a current-student checklist.
2. **The privacy default wins.** Their `personalization_opt_out` defaults to
   "personalise"; ours defaults to "do not". See `_personalization`.
3. **Asymmetry is documented, not hidden.** Three mappings cannot make the round
   trip intact (`technical_proficiency`, `target_roles`,
   `consent_flags.personalization`) and one cannot be expressed in their
   vocabulary at all (`lifecycle_stage.graduating`). Each is spelled out on
   `to_rag_data`.

This module deliberately imports nothing but `common.profile`: it must stay
usable from the Flask side, the FastAPI side and plain tests alike.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from common.profile import (
    AcademicBackground,
    ConsentFlags,
    DegreeLevel,
    FieldOfStudy,
    LifecycleStage,
    Proficiency,
    TargetRole,
    UserProfile,
)


class ProfileMappingError(ValueError):
    """A value that cannot be carried across the rag-data <-> authority boundary.

    Subclasses ValueError so a pydantic validator can surface it as a 422 and so
    existing `except ValueError` callers keep working. Carries `field` and
    `value` as attributes because an error message alone is not something a
    caller can branch on.
    """

    def __init__(self, field: str, value: object, reason: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"{field}={value!r}: {reason}")


# ---------- controlled vocabularies ----------
# Their stage words -> ours. Source: rag-data/scripts/profile_extract.py
# LIFECYCLE_STAGES (5 values) plus `student`, which is the chat frontend's word
# for the same state (see app/api/chat.py). Decision 1: the authority keeps its 6
# values and the aliases live here, at the boundary, never as extra enum members.
RAG_STAGE_TO_AUTHORITY: dict[str, LifecycleStage] = {
    "prospect": LifecycleStage.prospect,
    "applicant": LifecycleStage.applicant,
    "admitted": LifecycleStage.admitted,
    "enrolled": LifecycleStage.current,
    "student": LifecycleStage.current,
    "alumni": LifecycleStage.alumni,
}

# Ours -> theirs. `graduating` maps to None on purpose: their five-value
# vocabulary has no word for it, and None is their own "not stated" value (see
# EMPTY_PROFILE in their extractor). Emitting `enrolled` instead would tell their
# retrieval side that a graduating student is mid-programme, which produces
# confidently wrong course advice. The cost is that a graduating profile pushed
# to their store cannot be read back as graduating -- `from_rag_data` raises on
# the missing stage rather than inventing one, so the loss is loud on return.
AUTHORITY_STAGE_TO_RAG: dict[LifecycleStage, str | None] = {
    LifecycleStage.prospect: "prospect",
    LifecycleStage.applicant: "applicant",
    LifecycleStage.admitted: "admitted",
    LifecycleStage.current: "enrolled",
    LifecycleStage.graduating: None,
    LifecycleStage.alumni: "alumni",
}

# Their 3-level tech scale (profile_extract.py TECH_LEVELS) -> our 4 levels.
# Decision 2: the authority keeps 4 levels; `strong` is widened here only.
RAG_TECH_TO_AUTHORITY: dict[str, Proficiency] = {
    "none": Proficiency.none,
    "basic": Proficiency.basic,
    "strong": Proficiency.advanced,
}

# Outbound. LOSSY: their scale cannot distinguish intermediate from advanced, so
# both collapse to `strong`. See to_rag_data's docstring.
AUTHORITY_TECH_TO_RAG: dict[Proficiency, str] = {
    Proficiency.none: "none",
    Proficiency.basic: "basic",
    Proficiency.intermediate: "strong",
    Proficiency.advanced: "strong",
}

# Derived from the enums, never re-typed as literals: a second copy of a
# vocabulary is exactly how these four profile definitions drifted apart.
_FIELD_OF_STUDY_BY_STD: dict[str, FieldOfStudy] = {e.value: e for e in FieldOfStudy}
_TARGET_ROLE_BY_ID: dict[str, TargetRole] = {e.value: e for e in TargetRole}

# `UserProfile.raw_inputs` keys. The user's own wording is stored under the name
# of the authority field it was mapped into, so `to_rag_data` can rebuild their
# `{raw, std}` pairs without a parallel `*_raw` column per field.
RAW_ACADEMIC_BACKGROUND = "academic_background"
RAW_TECHNICAL_PROFICIENCY = "technical_proficiency"
RAW_TARGET_ROLES = "target_roles"
RAW_TARGET_INDUSTRY = "target_industry"

RAG_OPT_OUT_KEY = "personalization_opt_out"


# ---------- primitives ----------
def _accepted(table: Mapping[Any, Any]) -> str:
    return ", ".join(str(getattr(key, "value", key)) for key in table)


def _mapped(field: str, key: object, table: Mapping[Any, Any]) -> Any:
    """Look `key` up in a mapping table, or raise naming the field and value.

    The only lookup helper in this module, used in both directions. TypeError is
    caught because an unhashable incoming value (a list where a word belongs)
    must fail the same explicit way an unknown word does.
    """
    try:
        return table[key]
    except (KeyError, TypeError):
        raise ProfileMappingError(
            field, key, f"no mapping defined; accepted: {_accepted(table)}"
        ) from None


def _pair(src: Mapping[str, Any], key: str) -> tuple[str | None, str | None]:
    """Split one of their `{raw, std}` fields into (raw, std)."""
    value = src.get(key)
    if value is None:
        return None, None
    if not isinstance(value, Mapping):
        raise ProfileMappingError(key, value, "expected a {raw, std} object")
    return value.get("raw") or None, value.get("std") or None


def _intake_year(value: object) -> int | None:
    """Their intake year is a string ("2026"); ours is an int.

    Only the shape is converted here. The calendar-year range is owned by
    `UserProfile.intake_year` so the bound lives in exactly one place; an
    out-of-range year surfaces as a pydantic ValidationError naming the value.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass; a flag is not a year
        raise ProfileMappingError("intake_year", value, "expected a four-digit year")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ProfileMappingError("intake_year", value, "expected a four-digit year")


def _personalization(src: Mapping[str, Any]) -> bool:
    """Their opt-OUT switch -> our opt-IN flag: negated, and default-safe.

    Their default (no key recorded) means "personalise"; ours means "do not".
    An unrecorded flag is therefore NOT translated to True -- doing so would
    silently switch personalisation on for every user in their store who never
    expressed a choice, which is a privacy-default regression, not a naming nit.
    Only an explicitly recorded `false` ("the user did not opt out") turns it on.
    """
    recorded = src.get(RAG_OPT_OUT_KEY)
    if recorded is None:  # absent, or present-and-null: no choice was recorded
        return False
    if not isinstance(recorded, bool):
        raise ProfileMappingError(RAG_OPT_OUT_KEY, recorded, "expected a boolean")
    return not recorded


def _academic_background(
    src: Mapping[str, Any], degree_level: DegreeLevel | None
) -> AcademicBackground | None:
    """Their `academic_background.std` -> the authority sub-object.

    Raises when a field of study is present but no degree level was supplied:
    `AcademicBackground.degree_level` is required and the rag-data schema carries
    no such field, so the only alternatives would be to invent a credential the
    user never claimed or to drop the field of study on the floor.
    """
    _, std = _pair(src, "academic_background")
    if std is None:
        return None
    field_of_study = _mapped("academic_background.std", std, _FIELD_OF_STUDY_BY_STD)
    if degree_level is None:
        raise ProfileMappingError(
            "academic_background.degree_level",
            None,
            "the authority model requires a degree level and the rag-data schema "
            "carries none; pass degree_level=... instead of assuming one",
        )
    return AcademicBackground(degree_level=degree_level, field_of_study=field_of_study)


def _target_roles(src: Mapping[str, Any]) -> list[TargetRole]:
    """Their single `target_role_std` -> our ordered list (0 or 1 element)."""
    std = src.get("target_role_std")
    if std is None:
        return []
    return [_mapped("target_role_std", std, _TARGET_ROLE_BY_ID)]


def _raw_inputs(src: Mapping[str, Any]) -> dict[str, str]:
    """Preserve the user's own wording, keyed by the authority field it fed."""
    wording = {
        RAW_ACADEMIC_BACKGROUND: _pair(src, "academic_background")[0],
        RAW_TECHNICAL_PROFICIENCY: _pair(src, "tech_level")[0],
        RAW_TARGET_ROLES: src.get("target_role_raw") or None,
        RAW_TARGET_INDUSTRY: _pair(src, "target_industry")[0],
    }
    return {field: text for field, text in wording.items() if text is not None}


# ---------- inbound: rag-data -> authority ----------
def from_rag_data(
    src: Mapping[str, Any],
    *,
    user_id: str,
    degree_level: DegreeLevel | None = None,
) -> UserProfile:
    """Build the authority profile from one stored rag-data profile.

    `user_id` is the storage key the profile was read under; it is required
    because their extractor output does not carry one. If the stored blob also
    carries a `user_id` and the two disagree, that is a mixed-up profile and it
    raises rather than picking a winner.

    `degree_level` is only consulted when the profile states a field of study --
    see `_academic_background` for why it cannot be guessed.

    Raises ProfileMappingError for an unknown or missing `lifecycle_stage`, an
    unknown tech level, field of study or target role, a non-boolean opt-out
    flag, or a malformed `{raw, std}` object. Stage and tech words are matched
    exactly, without case folding: their `_sanitize` already emits lower-case
    vocabulary values, so a differently-cased word means drift somewhere and
    should be seen.
    """
    stored_id = src.get("user_id")
    if stored_id is not None and stored_id != user_id:
        raise ProfileMappingError(
            "user_id", stored_id, f"does not match the requested user_id {user_id!r}"
        )
    stage_word = src.get("lifecycle_stage")
    if stage_word is None:
        raise ProfileMappingError(
            "lifecycle_stage",
            None,
            "the authority model requires a stage; their extractor leaves it null "
            "when the user has not stated one, so ask rather than assume",
        )
    _, tech_std = _pair(src, "tech_level")
    _, industry_std = _pair(src, "target_industry")
    return UserProfile(
        user_id=user_id,
        lifecycle_stage=_mapped("lifecycle_stage", stage_word, RAG_STAGE_TO_AUTHORITY),
        academic_background=_academic_background(src, degree_level),
        work_years=src.get("work_years"),
        technical_proficiency=(
            _mapped("tech_level.std", tech_std, RAG_TECH_TO_AUTHORITY)
            if tech_std is not None
            else None
        ),
        target_roles=_target_roles(src),
        consent_flags=ConsentFlags(personalization=_personalization(src)),
        intake_year=_intake_year(src.get("intake_year")),
        application_term=src.get("application_term"),
        gmat=src.get("gmat"),
        gre=src.get("gre"),
        toefl=src.get("toefl"),
        ielts=src.get("ielts"),
        # Absent and null both mean "no topics recorded"; this is a null-to-empty
        # identity, not a fallback for an unmappable value.
        asked_topics=src.get("asked_topics") or [],
        updated_at=src.get("updated_at"),
        school_tier=src.get("school_tier"),
        target_industry=industry_std,
        raw_inputs=_raw_inputs(src),
    )


# ---------- outbound: authority -> rag-data ----------
def to_rag_data(profile: UserProfile) -> dict[str, Any]:
    """Render the authority profile in their schema's shape (doc section 四).

    Fields of ours that their schema has no slot for (`authenticated`, `email`,
    `country`, `work_domain`, `finance_knowledge`, `preferred_learning_style`,
    `application_type`, `completed_modules`, `application`, notification
    settings) are simply not emitted; nothing on their side reads them.

    Four asymmetries, none of them silent:

    * `technical_proficiency` -- **LOSSY**. Their scale has three levels, ours
      four, so `intermediate` and `advanced` both leave as `strong`. This does
      not round-trip: `strong` read back becomes `advanced`, so an intermediate
      user is promoted. Do not treat authority -> rag -> authority as identity
      for this field.
    * `lifecycle_stage` -- `graduating` leaves as None, their "not stated"
      value, because their vocabulary cannot express it. Never as `enrolled`.
    * `target_roles` -- **LOSSY** past the first entry. Their
      `target_role_std` is a single slot, so only `target_roles[0]` is emitted;
      any further roles are dropped. Index 0 is the primary role by the
      authority's own convention (an explicit override leads the list, see
      `student/api2.py:_ordered_target_roles`). The dropped roles are not folded
      into `target_role_raw`, which holds the user's own words and must stay
      exactly what they typed.
    * `consent_flags.personalization` -- **NOT EXACT**, and the choice here is
      deliberate. Their field has three states (key absent or null = no choice
      recorded, `false` = the user did not opt out, `true` = the user opted
      out); ours has two, and `False` covers both "the user declined" and "the
      user was never asked". The key is therefore emitted unconditionally as
      `not personalization`, which never moves anyone towards personalisation.
      Omitting it when we hold no consent would read as more honest but is
      strictly worse: a recorded `true` arrives as `False` exactly like "never
      asked", so omitting would drop a real opt-out and their missing-key
      default ("personalise") would switch personalisation back on -- the
      privacy regression `_personalization` exists to prevent, in the other
      direction. The accepted cost is that a profile which recorded no choice
      returns carrying `personalization_opt_out: true`, a decision the user
      never made, so their settings page must not render it as one. Separating
      the two states needs a third value on `ConsentFlags.personalization`;
      that is the authority model owner's call, not this adapter's.
    """
    academic = profile.academic_background
    tech = profile.technical_proficiency
    return {
        "user_id": profile.user_id,
        "academic_background": {
            "raw": profile.raw_inputs.get(RAW_ACADEMIC_BACKGROUND),
            "std": academic.field_of_study.value if academic else None,
        },
        "school_tier": profile.school_tier,
        "tech_level": {
            "raw": profile.raw_inputs.get(RAW_TECHNICAL_PROFICIENCY),
            "std": _mapped("technical_proficiency", tech, AUTHORITY_TECH_TO_RAG)
            if tech is not None
            else None,
        },
        "work_years": profile.work_years,
        "gmat": profile.gmat,
        "gre": profile.gre,
        "toefl": profile.toefl,
        "ielts": profile.ielts,
        "target_role_raw": profile.raw_inputs.get(RAW_TARGET_ROLES),
        "target_role_std": (
            profile.target_roles[0].value if profile.target_roles else None
        ),
        "target_industry": {
            "raw": profile.raw_inputs.get(RAW_TARGET_INDUSTRY),
            "std": profile.target_industry,
        },
        "lifecycle_stage": _mapped(
            "lifecycle_stage", profile.lifecycle_stage, AUTHORITY_STAGE_TO_RAG
        ),
        "application_term": profile.application_term,
        "intake_year": (
            str(profile.intake_year) if profile.intake_year is not None else None
        ),
        "asked_topics": list(profile.asked_topics),
        "updated_at": profile.updated_at,
        # Negated, and note the default flips with it: our unset personalization
        # (False) means we must tell their side to opt the user OUT. Emitted
        # unconditionally even though `False` cannot say whether a choice was
        # ever recorded -- see the personalization bullet above for why omitting
        # the key would lose a real opt-out.
        RAG_OPT_OUT_KEY: not profile.consent_flags.personalization,
    }
