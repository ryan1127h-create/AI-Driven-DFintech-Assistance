"""Tests for common.skill_taxonomy."""
from __future__ import annotations

from common.skill_taxonomy import SkillDef, load_taxonomy


def test_loads_skills():
    skills = load_taxonomy()
    assert len(skills) >= 9
    assert all(isinstance(s, SkillDef) for s in skills)


def test_covers_role_required_skills():
    import json
    from pathlib import Path
    rm = json.loads(Path("data/role_module_map.json").read_text(encoding="utf-8"))
    required = {s for role in rm["roles"].values() for s in role["required_skills"]}
    ids = {s.id for s in load_taxonomy()}
    assert required <= ids, f"taxonomy missing: {required - ids}"


def test_skill_fields_populated():
    s = next(s for s in load_taxonomy() if s.id == "risk_modeling")
    assert s.label == "风险建模"
    assert s.description
    assert s.framework.get("esco")
    assert "quantitative risk" in s.aliases
