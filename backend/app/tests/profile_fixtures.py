"""A small, realistic slice of profile.field_definitions for the profile
validation/service tests — same keys and shapes as the live dictionary."""

from __future__ import annotations

ROLE_TAGS = {"data_analytics": "Data Analytics", "blockchain": "Blockchain", "product_business": "Product & Business"}
PROGRAM_OPTIONS = {"hkust_msc_fintech": "HKUST MSc(FinTech)", "ntu_msc_fintech": "NTU MSc FinTech"}


def _d(key, value_type, *, module="E", storage="value", layer="declared", sources=("QA",),
       allowed=None, labels=None, values_ref=None, max_items=None, expiry=None, visible=True, label=None):
    return {
        "field_key": key, "module": module, "label": label or key,
        "value_type": value_type, "allowed_values": allowed, "value_labels": labels,
        "values_ref": values_ref,
        "max_items": max_items, "tier": "P1", "tier_condition": None, "sources": list(sources),
        "layer": layer, "extraction_type": None, "purpose_tags": ["course"], "stages": ["PRO"],
        "expiry_rule": expiry, "storage": storage, "user_visible": visible, "value_spec": None,
        "description": None, "schema_version": "4.2",
    }


DEFINITIONS = {d["field_key"]: d for d in [
    _d("lifecycle_stage", "single", module="A", sources=("QA", "DB"), label="Lifecycle stage",
       allowed=["prospect", "applicant", "admitted", "current", "graduating", "alumni"]),
    _d("study_mode", "single", module="A", sources=("QA", "DB"), allowed=["full_time", "part_time", "undecided"]),
    _d("sub_stage", "single", module="A", layer="inferred", sources=("DB", "DER"), allowed=["SUBMITTED", "ACCEPTED"]),
    _d("intake_term", "term", module="A", sources=("QA", "DB")),
    _d("languages", "multi", module="B", sources=("CV", "QA")),
    _d("is_nus_alumnus", "bool", module="B", sources=("QA", "DB")),
    _d("bachelor_grad_year", "year", module="C", sources=("CV",)),
    _d("degree_discipline_category", "single", module="C", sources=("CV",), allowed=["cs_se", "engineering"]),
    _d("seniority_level", "single", module="D", allowed=["none", "junior", "mid_senior", "management"]),
    _d("admission_tests", "structured", sources=("CV", "QA"), allowed=["GRE", "GMAT", "TOEFL", "IELTS"],
       expiry={"per_item_by": "test_date", "validity_years": {"GRE": 5, "GMAT": 5, "IELTS": 2, "TOEFL": 2}}),
    _d("code_level", "single", sources=("QA", "CV"), allowed=[0, 1, 2, 3, 4],
       labels={"2": "Has written data-processing scripts independently"}, label="Programming proficiency"),
    _d("certifications", "multi", sources=("CV", "QA"), allowed=["cfa", "frm", "other"]),
    _d("target_markets", "multi", module="F", allowed=["SG", "CN", "US", "ANY"]),
    _d("target_role_families", "multi", module="F", values_ref="knowledge.tags_definition",
       label="Target role families"),
    _d("main_target_role", "single", module="F", values_ref="knowledge.tags_definition",
       label="Main target role"),
    _d("career_goal_clarity", "single", module="F", allowed=["clear", "few_options", "exploring"]),
    _d("decision_factors", "multi", module="H", allowed=["cost", "duration", "tech_depth", "scholarship"], max_items=3),
    _d("competing_programs", "multi", module="H", values_ref="program.programs", max_items=5,
       label="Programmes being compared"),
    _d("current_position", "structured", module="J", sources=("QA", "CV")),
    _d("currently_hiring", "structured", module="J"),
    _d("application_record", "structured", module="H", storage="sis", layer="evidence", sources=("DB",),
       label="Application record"),
    _d("current_modules", "list", module="I", storage="sis", layer="evidence", sources=("DB",), label="Current courses"),
    _d("academic_standing", "single", module="I", storage="sis", layer="evidence", sources=("DB",), visible=False),
    _d("drop_off_risk", "single", module="M", storage="derived", layer="inferred", sources=("DER",), visible=False),
    _d("motivation_segment", "single", module="M", storage="derived", layer="inferred", sources=("DER",)),
    _d("language_pref", "multi", module="K", storage="account"),
    _d("consent_personalized_rec", "bool", module="L", storage="consent", label="Personalised recommendations"),
]}


def entry(value, source="QA", *, verified=False):
    """One v_profile row, as repository.get_profile() returns it."""
    return {"value": value, "source": source, "verified": verified, "updated_at": None}
