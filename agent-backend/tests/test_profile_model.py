"""Tests for common.profile as the single authoritative user profile.

Covers the fields imported from the rag-data extraction pipeline
(rag-data/docs/user_profile_schema.md): they must be optional with safe
defaults, must not silently coerce bad input, and must carry the user's
original wording without loss.
"""
import json

import pytest
from pydantic import ValidationError

from common.profile import (
    FieldOfStudy,
    LifecycleStage,
    Proficiency,
    TargetRole,
    UserProfile,
)

# The rag-data pipeline's own vocabulary (rag-data/scripts/profile_extract.py
# CAREER_ROLES). Duplicated here on purpose: rag-data is a separate, read-only
# repo area, so this list is the contract, and this test is what tells us if
# either side drifts.
RAG_DATA_CAREER_ROLES = [
    "quant_risk",
    "data_analytics",
    "fintech_pm",
    "payments",
    "digital_banking",
    "compliance_regtech",
]


def _minimal() -> UserProfile:
    """A profile built the way every pre-existing caller builds one."""
    return UserProfile(user_id="u1", lifecycle_stage=LifecycleStage.applicant)


# ---------- new fields are optional with safe defaults ----------
def test_rag_data_fields_all_default_to_empty():
    p = _minimal()  # constructing without them at all must still work
    assert p.intake_year is None
    assert p.application_term is None
    assert p.gmat is None
    assert p.gre is None
    assert p.toefl is None
    assert p.ielts is None
    assert p.asked_topics == []
    assert p.updated_at is None
    assert p.school_tier is None
    assert p.target_industry is None
    assert p.raw_inputs == {}


# ---------- privacy default (decision 3) ----------
def test_personalization_is_opt_in_by_default():
    assert _minimal().consent_flags.personalization is False


def test_reminders_and_alumni_matching_are_also_opt_in():
    flags = _minimal().consent_flags
    assert flags.reminders is False
    assert flags.alumni_matching is False


# ---------- no silent coercion at the boundary ----------
def test_intake_year_rejects_a_non_year_instead_of_defaulting():
    with pytest.raises(ValidationError) as exc:
        UserProfile(user_id="u1", lifecycle_stage=LifecycleStage.admitted, intake_year=25)
    assert "25" in str(exc.value)  # the offending value is reported


def test_intake_year_accepts_any_four_digit_year():
    # No expiring window: a future intake must not need a code change.
    for year in (2025, 2027, 2031):
        p = UserProfile(
            user_id="u1", lifecycle_stage=LifecycleStage.admitted, intake_year=year
        )
        assert p.intake_year == year


def test_negative_test_scores_are_rejected():
    for field in ("gmat", "gre", "toefl", "ielts"):
        with pytest.raises(ValidationError):
            UserProfile(
                user_id="u1", lifecycle_stage=LifecycleStage.applicant, **{field: -1}
            )


def test_ielts_keeps_half_bands():
    p = UserProfile(user_id="u1", lifecycle_stage=LifecycleStage.applicant, ielts=6.5)
    assert p.ielts == 6.5  # an int field would truncate this to 6


def test_gmat_rejects_a_fractional_score():
    with pytest.raises(ValidationError):
        UserProfile(user_id="u1", lifecycle_stage=LifecycleStage.applicant, gmat=680.5)


# ---------- raw wording round-trip (rag-data {raw, std} pairs) ----------
# Example profile from rag-data/docs/user_profile_schema.md §四. Only the `std`
# values that are already identical on both sides are used, so this test proves
# losslessness without encoding any mapping decision (mapping is the adapter's
# job, built separately).
RAG_DATA_PROFILE = {
    "user_id": "u_12345",
    "academic_background": {"raw": "金融本科", "std": "finance"},
    "school_tier": "双非",
    "tech_level": {"raw": "会一点 Python", "std": "basic"},
    "work_years": 2,
    "gmat": 680,
    "gre": None,
    "toefl": 100,
    "ielts": None,
    "target_role_raw": "想做量化风险那种",
    "target_role_std": "quant_risk",
    "target_industry": {"raw": "投行", "std": "banking"},
    "lifecycle_stage": "applicant",
    "application_term": "2026 Fall",
    "intake_year": None,
    "asked_topics": ["tuition", "course_planning"],
    "updated_at": "2026-07-22T14:30:00Z",
}


def _authority_from_rag_data(src: dict) -> UserProfile:
    """Narrow, test-local load of the rag-data shape into the authority model."""
    raw_inputs = {
        "academic_background": src["academic_background"]["raw"],
        "technical_proficiency": src["tech_level"]["raw"],
        "target_roles": src["target_role_raw"],
        "target_industry": src["target_industry"]["raw"],
    }
    return UserProfile(
        user_id=src["user_id"],
        lifecycle_stage=LifecycleStage(src["lifecycle_stage"]),
        academic_background={
            "degree_level": "bachelor",
            "field_of_study": FieldOfStudy(src["academic_background"]["std"]),
        },
        work_years=src["work_years"],
        technical_proficiency=Proficiency(src["tech_level"]["std"]),
        target_roles=[TargetRole(src["target_role_std"])],
        school_tier=src["school_tier"],
        target_industry=src["target_industry"]["std"],
        gmat=src["gmat"],
        gre=src["gre"],
        toefl=src["toefl"],
        ielts=src["ielts"],
        application_term=src["application_term"],
        intake_year=src["intake_year"],
        asked_topics=src["asked_topics"],
        updated_at=src["updated_at"],
        raw_inputs=raw_inputs,
    )


def test_rag_data_profile_round_trips_without_losing_user_wording():
    loaded = _authority_from_rag_data(RAG_DATA_PROFILE)

    # Through JSON, because the storage layer for these profiles is Redis.
    restored = UserProfile.model_validate_json(loaded.model_dump_json())

    # 1. Every original phrase comes back byte-for-byte.
    assert restored.raw_inputs["academic_background"] == "金融本科"
    assert restored.raw_inputs["technical_proficiency"] == "会一点 Python"
    assert restored.raw_inputs["target_roles"] == "想做量化风险那种"
    assert restored.raw_inputs["target_industry"] == "投行"

    # 2. The typed (std) side survives too.
    assert restored.academic_background.field_of_study is FieldOfStudy.finance
    assert restored.technical_proficiency is Proficiency.basic
    assert restored.target_roles == [TargetRole.quant_risk]

    # 3. Rebuilding the rag-data {raw, std} shape reproduces the source exactly.
    rebuilt = {
        "academic_background": {
            "raw": restored.raw_inputs.get("academic_background"),
            "std": restored.academic_background.field_of_study.value,
        },
        "tech_level": {
            "raw": restored.raw_inputs.get("technical_proficiency"),
            "std": restored.technical_proficiency.value,
        },
        "target_role_raw": restored.raw_inputs.get("target_roles"),
        "target_role_std": restored.target_roles[0].value,
        "target_industry": {
            "raw": restored.raw_inputs.get("target_industry"),
            "std": restored.target_industry,
        },
    }
    assert rebuilt["academic_background"] == RAG_DATA_PROFILE["academic_background"]
    assert rebuilt["tech_level"] == RAG_DATA_PROFILE["tech_level"]
    assert rebuilt["target_role_raw"] == RAG_DATA_PROFILE["target_role_raw"]
    assert rebuilt["target_role_std"] == RAG_DATA_PROFILE["target_role_std"]
    assert rebuilt["target_industry"] == RAG_DATA_PROFILE["target_industry"]


def test_scalar_rag_data_fields_round_trip_unchanged():
    restored = UserProfile.model_validate_json(
        _authority_from_rag_data(RAG_DATA_PROFILE).model_dump_json()
    )
    assert restored.gmat == 680
    assert restored.gre is None
    assert restored.toefl == 100
    assert restored.school_tier == "双非"
    assert restored.application_term == "2026 Fall"
    assert restored.intake_year is None
    assert restored.asked_topics == ["tuition", "course_planning"]
    assert restored.updated_at == "2026-07-22T14:30:00Z"


def test_raw_inputs_survives_plain_json_dump():
    # The settings page reads the dumped dict, not the model object.
    dumped = json.loads(_authority_from_rag_data(RAG_DATA_PROFILE).model_dump_json())
    assert dumped["raw_inputs"]["technical_proficiency"] == "会一点 Python"


# ---------- vocabulary already shared with rag-data ----------
def test_target_role_ids_match_rag_data_career_roles():
    # Renaming a TargetRole member would silently break the teammate's
    # career_roles retrieval, which keys on these exact ids.
    assert {r.value for r in TargetRole} == set(RAG_DATA_CAREER_ROLES)


def test_lifecycle_stage_has_no_back_door_aliases():
    # Decision 1: `enrolled` / `student` are mapped by the adapter, never
    # accepted as enum values, so an unmapped stage cannot slip through.
    assert [s.value for s in LifecycleStage] == [
        "prospect",
        "applicant",
        "admitted",
        "current",
        "graduating",
        "alumni",
    ]
    for unmapped in ("enrolled", "student"):
        with pytest.raises(ValueError):
            LifecycleStage(unmapped)
