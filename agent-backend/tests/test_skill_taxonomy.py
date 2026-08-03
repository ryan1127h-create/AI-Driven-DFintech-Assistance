"""Tests for common.skill_taxonomy."""
from __future__ import annotations

import json
import re
from pathlib import Path

from common.skill_taxonomy import SkillDef, load_taxonomy

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_loads_skills():
    skills = load_taxonomy()
    assert len(skills) >= 9
    assert all(isinstance(s, SkillDef) for s in skills)


def test_covers_role_required_skills():
    # Resolved from the test file, not the cwd, so the suite can run from any dir.
    rm = json.loads((_DATA_DIR / "role_module_map.json").read_text(encoding="utf-8"))
    required = {s for role in rm["roles"].values() for s in role["required_skills"]}
    ids = {s.id for s in load_taxonomy()}
    assert required <= ids, f"taxonomy missing: {required - ids}"


def test_skill_fields_populated():
    s = next(s for s in load_taxonomy() if s.id == "risk_modeling")
    assert s.label == "Risk modelling"
    assert s.description
    assert s.framework.get("esco")
    assert "quantitative risk" in s.aliases


def test_taxonomy_text_is_english_only():
    # Labels/aliases/descriptions feed the skill embedding text; residual Chinese
    # strings would pollute it after the English migration.
    cjk = re.compile(r"[　-〿一-鿿＀-￯]")
    for s in load_taxonomy():
        blob = " ".join([s.label, s.description, *s.aliases])
        assert not cjk.search(blob), f"{s.id} still contains Chinese text"
