"""Tests for the rag-data <-> authority profile adapter.

Every mapping decision in common/profile_adapter.py is pinned here, and every
test was mutation-checked (see the task report). The two real fixtures under
rag-data/data/ are loaded from disk rather than re-typed, so a change on the
teammate's side shows up as a failure here.
"""
import json
from pathlib import Path

import pytest

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
from common.profile_adapter import (
    AUTHORITY_STAGE_TO_RAG,
    AUTHORITY_TECH_TO_RAG,
    RAG_OPT_OUT_KEY,
    RAG_STAGE_TO_AUTHORITY,
    RAG_TECH_TO_AUTHORITY,
    ProfileMappingError,
    from_rag_data,
    to_rag_data,
)

RAG_DATA = Path(__file__).resolve().parents[2] / "rag-data" / "data"
USER = "u_test"

# Their extractor's fallback shape (rag-data/scripts/profile_extract.py
# EMPTY_PROFILE). Re-typed here on purpose: rag-data is a separate, read-only
# repo area, so this literal is the contract and
# test_empty_profile_shape_still_matches_their_fixtures is what tells us if
# either side drifts.
RAG_EMPTY_PROFILE = {
    "lifecycle_stage": None,
    "academic_background": {"raw": None, "std": None},
    "tech_level": {"raw": None, "std": None},
    "gmat": None,
    "gre": None,
    "toefl": None,
    "ielts": None,
    "target_role_raw": None,
    "target_role_std": None,
    "application_term": None,
    "intake_year": None,
}

# rag-data/scripts/profile_extract.py LIFECYCLE_STAGES and TECH_LEVELS, likewise
# re-typed as the contract under test.
RAG_LIFECYCLE_STAGES = ["prospect", "applicant", "admitted", "enrolled", "alumni"]
RAG_TECH_LEVELS = ["none", "basic", "strong"]

# The full profile from rag-data/docs/user_profile_schema.md section 四: every
# key their storage layer holds, not just the 11 their extractor emits.
RAG_FULL_PROFILE = {
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
    RAG_OPT_OUT_KEY: False,
}


def _load(name: str) -> dict:
    path = RAG_DATA / name
    assert path.exists(), f"missing real fixture {path}; it is the contract under test"
    return json.loads(path.read_text(encoding="utf-8"))


def _rag(**overrides) -> dict:
    """A minimal valid rag-data profile: only a stage, plus any overrides."""
    return {"lifecycle_stage": "applicant", **overrides}


def _authority(**overrides) -> UserProfile:
    base = {"user_id": USER, "lifecycle_stage": LifecycleStage.current}
    return UserProfile(**{**base, **overrides})


# ---------- lifecycle_stage inbound (decision 1) ----------
def test_enrolled_maps_to_current():
    profile = from_rag_data(_rag(lifecycle_stage="enrolled"), user_id=USER)
    assert profile.lifecycle_stage is LifecycleStage.current


def test_student_maps_to_current():
    profile = from_rag_data(_rag(lifecycle_stage="student"), user_id=USER)
    assert profile.lifecycle_stage is LifecycleStage.current


@pytest.mark.parametrize("word", ["prospect", "applicant", "admitted", "alumni"])
def test_the_other_four_stages_are_carried_through_unchanged(word):
    profile = from_rag_data(_rag(lifecycle_stage=word), user_id=USER)
    assert profile.lifecycle_stage.value == word


def test_unknown_stage_raises_naming_the_received_value():
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(lifecycle_stage="alumnus"), user_id=USER)
    assert exc.value.field == "lifecycle_stage"
    assert exc.value.value == "alumnus"
    assert "alumnus" in str(exc.value)


def test_missing_stage_raises_instead_of_defaulting():
    # Their extractor leaves the stage null when the user has not stated one.
    # Coercing that to prospect/current would advise a user we cannot identify.
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(RAG_EMPTY_PROFILE, user_id=USER)
    assert exc.value.field == "lifecycle_stage"
    assert exc.value.value is None


@pytest.mark.parametrize("word", ["current", "graduating"])
def test_our_own_stage_words_are_not_accepted_inbound(word):
    # Their vocabulary does not contain these. Accepting them here would create a
    # second, undocumented path into the enum that bypasses the alias table.
    with pytest.raises(ProfileMappingError):
        from_rag_data(_rag(lifecycle_stage=word), user_id=USER)


def test_inbound_stage_table_covers_their_vocabulary_plus_the_chat_alias():
    assert set(RAG_STAGE_TO_AUTHORITY) == set(RAG_LIFECYCLE_STAGES) | {"student"}


# ---------- lifecycle_stage outbound ----------
def test_current_leaves_as_their_word_enrolled():
    assert to_rag_data(_authority())["lifecycle_stage"] == "enrolled"


def test_graduating_leaves_as_no_stage_and_never_as_enrolled():
    out = to_rag_data(_authority(lifecycle_stage=LifecycleStage.graduating))
    assert out["lifecycle_stage"] is None
    assert out["lifecycle_stage"] != "enrolled"


def test_graduating_cannot_be_read_back_and_says_so_loudly():
    # The loss is real, so it must surface on return rather than turning into
    # some other stage. This is the documented cost of their 5-value vocabulary.
    out = to_rag_data(_authority(lifecycle_stage=LifecycleStage.graduating))
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(out, user_id=USER)
    assert exc.value.field == "lifecycle_stage"


def test_outbound_stage_table_covers_every_authority_stage():
    # A stage added to the enum without a decision here would be a KeyError at
    # runtime instead of at review time.
    assert set(AUTHORITY_STAGE_TO_RAG) == set(LifecycleStage)


@pytest.mark.parametrize("word", ["prospect", "applicant", "admitted", "alumni"])
def test_the_four_shared_stages_round_trip(word):
    profile = from_rag_data(_rag(lifecycle_stage=word), user_id=USER)
    assert to_rag_data(profile)["lifecycle_stage"] == word


def test_enrolled_round_trips_through_current():
    profile = from_rag_data(_rag(lifecycle_stage="enrolled"), user_id=USER)
    assert to_rag_data(profile)["lifecycle_stage"] == "enrolled"


# ---------- technical proficiency (decision 2) ----------
def test_strong_widens_to_advanced():
    profile = from_rag_data(
        _rag(tech_level={"raw": "编程很熟", "std": "strong"}), user_id=USER
    )
    assert profile.technical_proficiency is Proficiency.advanced


@pytest.mark.parametrize("word", ["none", "basic"])
def test_none_and_basic_are_carried_through_unchanged(word):
    profile = from_rag_data(_rag(tech_level={"raw": "x", "std": word}), user_id=USER)
    assert profile.technical_proficiency.value == word


@pytest.mark.parametrize("word", ["intermediate", "advanced", "expert"])
def test_a_tech_word_outside_their_three_levels_raises(word):
    # `intermediate`/`advanced` are OUR words: their pipeline cannot emit them,
    # so seeing one means drift, not a value to be silently accepted.
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(tech_level={"raw": None, "std": word}), user_id=USER)
    assert exc.value.field == "tech_level.std"
    assert exc.value.value == word


def test_absent_tech_level_stays_unset():
    assert from_rag_data(_rag(), user_id=USER).technical_proficiency is None


def test_inbound_tech_table_covers_their_vocabulary_exactly():
    assert set(RAG_TECH_TO_AUTHORITY) == set(RAG_TECH_LEVELS)


@pytest.mark.parametrize(
    "level", [Proficiency.intermediate, Proficiency.advanced]
)
def test_both_upper_levels_collapse_to_strong_outbound(level):
    out = to_rag_data(_authority(technical_proficiency=level))
    assert out["tech_level"]["std"] == "strong"


def test_intermediate_is_promoted_to_advanced_by_a_round_trip():
    # Documented lossy direction. Asserted rather than glossed over: anyone who
    # believes this field round-trips will be wrong, and this is where they find
    # out instead of downstream in the course-difficulty filter.
    out = to_rag_data(_authority(technical_proficiency=Proficiency.intermediate))
    back = from_rag_data(out, user_id=USER)
    assert back.technical_proficiency is Proficiency.advanced


def test_outbound_tech_table_covers_every_authority_level():
    assert set(AUTHORITY_TECH_TO_RAG) == set(Proficiency)


# ---------- personalisation (decision 3: negated, privacy default wins) ----------
def test_an_unset_opt_out_arrives_as_personalisation_off():
    # Their default is "personalise"; ours is "do not". A profile that never
    # recorded a choice must NOT arrive personalised.
    assert RAG_OPT_OUT_KEY not in RAG_EMPTY_PROFILE  # the case really is unset
    profile = from_rag_data(_rag(), user_id=USER)
    assert profile.consent_flags.personalization is False


def test_a_null_opt_out_arrives_as_personalisation_off():
    profile = from_rag_data(_rag(**{RAG_OPT_OUT_KEY: None}), user_id=USER)
    assert profile.consent_flags.personalization is False


def test_an_explicitly_recorded_false_opt_out_enables_personalisation():
    profile = from_rag_data(_rag(**{RAG_OPT_OUT_KEY: False}), user_id=USER)
    assert profile.consent_flags.personalization is True


def test_an_explicitly_recorded_true_opt_out_disables_personalisation():
    profile = from_rag_data(_rag(**{RAG_OPT_OUT_KEY: True}), user_id=USER)
    assert profile.consent_flags.personalization is False


@pytest.mark.parametrize("junk", ["false", "no", 0, 1])
def test_a_non_boolean_opt_out_raises(junk):
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(**{RAG_OPT_OUT_KEY: junk}), user_id=USER)
    assert exc.value.field == RAG_OPT_OUT_KEY
    assert exc.value.value == junk


def test_our_default_profile_leaves_as_opted_out():
    # The authority default is personalization=False, so their side must be told
    # to opt the user out, not left on their permissive default.
    assert to_rag_data(_authority())[RAG_OPT_OUT_KEY] is True


def test_consented_personalisation_leaves_as_not_opted_out():
    profile = _authority(consent_flags=ConsentFlags(personalization=True))
    assert to_rag_data(profile)[RAG_OPT_OUT_KEY] is False


@pytest.mark.parametrize("consented", [True, False])
def test_a_recorded_personalisation_choice_survives_a_round_trip(consented):
    profile = _authority(consent_flags=ConsentFlags(personalization=consented))
    assert (
        from_rag_data(to_rag_data(profile), user_id=USER).consent_flags.personalization
        is consented
    )


@pytest.mark.parametrize("recorded", [True, False])
def test_a_recorded_opt_out_survives_the_return_trip_to_their_shape(recorded):
    # The rag -> authority -> rag direction, and the reason to_rag_data emits the
    # key unconditionally instead of omitting it when we hold no consent: a
    # recorded `true` arrives as personalization=False, indistinguishable from
    # "never asked". Omitting the key for False would therefore drop a real
    # opt-out, and their missing-key default ("personalise") would switch
    # personalisation back on for a user who had explicitly turned it off.
    out = to_rag_data(from_rag_data(_rag(**{RAG_OPT_OUT_KEY: recorded}), user_id=USER))
    assert out[RAG_OPT_OUT_KEY] is recorded


def test_a_profile_that_recorded_no_choice_returns_carrying_an_explicit_opt_out():
    # The accepted cost of a two-state authority flag meeting their three-state
    # field, asserted rather than glossed over: a stored profile that merely
    # passed through this backend comes back with an opt-out the user never
    # expressed. Their settings page must not render it as a user decision.
    source = _load("sample_profile_quant.json")
    assert RAG_OPT_OUT_KEY not in source  # no choice was ever recorded
    profile = from_rag_data(source, user_id=USER, degree_level=DegreeLevel.bachelor)
    assert to_rag_data(profile)[RAG_OPT_OUT_KEY] is True


# ---------- target role: single value <-> list ----------
def test_a_single_role_becomes_a_one_element_list():
    profile = from_rag_data(_rag(target_role_std="payments"), user_id=USER)
    assert profile.target_roles == [TargetRole.payments]


def test_a_null_role_becomes_an_empty_list():
    assert from_rag_data(_rag(), user_id=USER).target_roles == []


def test_an_unknown_role_id_raises_rather_than_being_dropped():
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(target_role_std="ml_engineer"), user_id=USER)
    assert exc.value.field == "target_role_std"
    assert exc.value.value == "ml_engineer"


def test_outbound_emits_the_first_role_and_drops_the_rest():
    profile = _authority(
        target_roles=[TargetRole.payments, TargetRole.quant_risk],
        raw_inputs={"target_roles": "支付，顺便量化"},
    )
    out = to_rag_data(profile)
    assert out["target_role_std"] == "payments"
    # The dropped role must not be smuggled into the user's own wording.
    assert out["target_role_raw"] == "支付，顺便量化"


def test_outbound_emits_no_role_when_none_is_set():
    assert to_rag_data(_authority())["target_role_std"] is None


# ---------- academic background ----------
def test_std_becomes_field_of_study_when_a_degree_level_is_stated():
    profile = from_rag_data(
        _rag(academic_background={"raw": "双非金融本科", "std": "finance"}),
        user_id=USER,
        degree_level=DegreeLevel.bachelor,
    )
    assert profile.academic_background.field_of_study is FieldOfStudy.finance
    assert profile.academic_background.degree_level is DegreeLevel.bachelor
    assert profile.raw_inputs["academic_background"] == "双非金融本科"


def test_a_field_of_study_without_a_degree_level_raises_instead_of_assuming_one():
    # Their schema carries no degree level and AcademicBackground requires one.
    # Inventing "bachelor" would be fabricating a credential.
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(
            _rag(academic_background={"raw": "金融本科", "std": "finance"}),
            user_id=USER,
        )
    assert exc.value.field == "academic_background.degree_level"


def test_an_unmapped_field_of_study_raises():
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(
            _rag(academic_background={"raw": "会计", "std": "accounting"}),
            user_id=USER,
            degree_level=DegreeLevel.bachelor,
        )
    assert exc.value.field == "academic_background.std"
    assert exc.value.value == "accounting"


def test_raw_wording_is_kept_even_when_there_is_no_std_to_map():
    profile = from_rag_data(
        _rag(academic_background={"raw": "还没想好", "std": None}), user_id=USER
    )
    assert profile.academic_background is None
    assert profile.raw_inputs["academic_background"] == "还没想好"


def test_a_raw_std_field_that_is_not_an_object_raises():
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(tech_level="strong"), user_id=USER)
    assert exc.value.field == "tech_level"
    assert exc.value.value == "strong"


# ---------- intake year ----------
def test_their_string_intake_year_becomes_an_int_and_returns_as_a_string():
    profile = from_rag_data(_rag(lifecycle_stage="admitted", intake_year="2026"), user_id=USER)
    assert profile.intake_year == 2026
    assert to_rag_data(profile)["intake_year"] == "2026"


@pytest.mark.parametrize("junk", ["Fall 2026", "", True, 20.26])
def test_a_non_year_intake_raises(junk):
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(intake_year=junk), user_id=USER)
    assert exc.value.field == "intake_year"


# ---------- user_id ----------
def test_a_stored_user_id_that_disagrees_with_the_key_raises():
    with pytest.raises(ProfileMappingError) as exc:
        from_rag_data(_rag(user_id="u_other"), user_id=USER)
    assert exc.value.field == "user_id"
    assert exc.value.value == "u_other"


def test_a_matching_stored_user_id_is_accepted():
    assert from_rag_data(_rag(user_id=USER), user_id=USER).user_id == USER


# ---------- shape contract with the teammate's pipeline ----------
def test_empty_profile_shape_still_matches_their_fixtures():
    # Both real fixtures are literally an EMPTY_PROFILE with values filled in.
    # If they add or rename a key, this is the failure that says so.
    for name in ("sample_profile_quant.json", "sample_profile_payments.json"):
        assert set(_load(name)) == set(RAG_EMPTY_PROFILE)


def test_an_empty_profile_with_a_stage_converts_to_an_all_default_profile():
    profile = from_rag_data({**RAG_EMPTY_PROFILE, "lifecycle_stage": "prospect"}, user_id=USER)
    assert profile.lifecycle_stage is LifecycleStage.prospect
    assert profile.academic_background is None
    assert profile.technical_proficiency is None
    assert profile.target_roles == []
    assert profile.raw_inputs == {}
    assert profile.consent_flags.personalization is False
    assert (profile.gmat, profile.gre, profile.toefl, profile.ielts) == (None,) * 4


# ---------- round trip on the real fixtures ----------
@pytest.mark.parametrize(
    "name", ["sample_profile_quant.json", "sample_profile_payments.json"]
)
def test_a_real_fixture_round_trips_without_losing_a_field(name):
    source = _load(name)
    profile = from_rag_data(source, user_id=USER, degree_level=DegreeLevel.bachelor)
    rebuilt = to_rag_data(profile)
    for key, expected in source.items():
        assert rebuilt[key] == expected, key


def test_the_full_documented_profile_round_trips_key_for_key():
    profile = from_rag_data(
        RAG_FULL_PROFILE, user_id="u_12345", degree_level=DegreeLevel.bachelor
    )
    assert to_rag_data(profile) == RAG_FULL_PROFILE


def test_the_round_trip_preserves_the_users_own_wording_byte_for_byte():
    source = _load("sample_profile_quant.json")
    profile = from_rag_data(source, user_id=USER, degree_level=DegreeLevel.bachelor)
    assert profile.raw_inputs["academic_background"] == "双非金融本科"
    assert profile.raw_inputs["technical_proficiency"] == "会一点Python"
    assert profile.raw_inputs["target_roles"] == "想做量化风险"


def _authority_with_extra_fields() -> UserProfile:
    return _authority(
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor, field_of_study=FieldOfStudy.finance
        ),
        country="SG",
        finance_knowledge=Proficiency.intermediate,
        completed_modules=["DFT5001"],
    )


def test_their_shape_has_no_slot_for_our_extra_fields_so_none_are_emitted():
    out = to_rag_data(_authority_with_extra_fields())
    for absent in ("country", "finance_knowledge", "completed_modules", "email"):
        assert absent not in out


def test_a_round_trip_through_their_shape_resets_our_extra_fields():
    # from_rag_data is a loader, not a merge: it builds a fresh profile. Fields
    # their schema cannot carry therefore come back at the authority defaults.
    # Asserted so nobody mistakes to_rag_data/from_rag_data for a lossless
    # round trip of the whole model -- a caller that must keep these has to
    # merge them itself.
    back = from_rag_data(
        to_rag_data(_authority_with_extra_fields()),
        user_id=USER,
        degree_level=DegreeLevel.bachelor,
    )
    assert back.country is None
    assert back.finance_knowledge is None
    assert back.completed_modules == []
