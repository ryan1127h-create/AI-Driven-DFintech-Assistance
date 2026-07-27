"""Curated skill taxonomy loader (design doc 13 §3).

Unifies the skill definitions previously scattered across navigator.skill_labels,
role_module_map required_skills, and comparator keywords. ids match the skill tags
in data/role_module_map.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "data" / "skill_taxonomy.json"


@dataclass(frozen=True)
class SkillDef:
    id: str
    label: str
    description: str
    aliases: tuple[str, ...] = ()
    framework: dict[str, str] = field(default_factory=dict)


def load_taxonomy() -> list[SkillDef]:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return [
        SkillDef(
            id=s["id"], label=s["label"], description=s["description"],
            aliases=tuple(s.get("aliases", [])), framework=dict(s.get("framework", {})),
        )
        for s in data["skills"]
    ]
