"""#7 Navigator engine: role -> modules + deterministic skill-gap.

The user's current skills are derived deterministically from profile fields
(technical proficiency, finance knowledge, work domain). Skill gap = a role's
required skills minus what the user already has.
"""
from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass, field
from pathlib import Path

from common import llm
from common.profile import Proficiency, TargetRole, UserProfile, WorkDomain
from common.skill_matcher import get_skill_matcher

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_MAP_PATH = _DATA_DIR / "role_module_map.json"
_CATALOG_PATH = _DATA_DIR / "module_catalog.json"
_MODULE_SKILLS_PATH = _DATA_DIR / "module_skills.json"

_VALID_SKILL_TAGS = {
    "programming", "data_analytics", "finance", "risk_modeling", "product",
    "regulation", "payments_systems", "security", "ai_ml",
}


def _load_module_skills() -> dict[str, list[str]]:
    """code -> [valid skill tags]. Unknown tags dropped; missing file -> {}."""
    if not _MODULE_SKILLS_PATH.exists():
        return {}
    try:
        raw = json.loads(_MODULE_SKILLS_PATH.read_text(encoding="utf-8")).get("modules", {})
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        code: [t for t in tags if t in _VALID_SKILL_TAGS]
        for code, tags in raw.items()
    }


def _load() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def _load_catalog() -> dict[str, dict]:
    """Return code -> authoritative module detail from the (refreshed) catalog.

    Empty if the catalog is missing, so recommendations still work (degraded to
    the role-map names).
    """
    if not _CATALOG_PATH.exists():
        return {}
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {m["code"]: m for m in data.get("modules", [])}


def _enrich_modules(modules: list[dict]) -> list[dict]:
    """Overlay authoritative name/credits/description from the catalog.

    Falls back to the role-map name when a code isn't in the catalog, and marks
    each entry `verified` so the UI can distinguish sourced data.
    """
    catalog = _load_catalog()
    out = []
    for m in modules:
        cat = catalog.get(m["code"])
        if cat:
            out.append({
                "code": m["code"],
                "name": cat.get("name") or m.get("name"),
                "credits": cat.get("credits"),
                "description": cat.get("description"),
                "source_url": cat.get("source_url"),
                "verified": True,
            })
        else:
            out.append({
                "code": m["code"],
                "name": m.get("name"),
                "credits": None,
                "description": None,
                "source_url": None,
                "verified": False,
            })
    return out


def derive_user_skills(profile: UserProfile) -> set[str]:
    """Map profile fields to a set of skill tags (deterministic, explainable)."""
    skills: set[str] = set()
    tech = profile.technical_proficiency
    if tech in (Proficiency.intermediate, Proficiency.advanced):
        skills.add("programming")
        skills.add("data_analytics")
    if tech == Proficiency.advanced:
        skills.add("risk_modeling")
        skills.add("ai_ml")
        skills.add("security")
    fin = profile.finance_knowledge
    if fin in (Proficiency.intermediate, Proficiency.advanced):
        skills.add("finance")
    if fin == Proficiency.advanced:
        skills.add("regulation")
    if profile.work_domain in (WorkDomain.banking, WorkDomain.fintech):
        skills.add("finance")
    if profile.work_domain == WorkDomain.fintech:
        skills.add("payments_systems")
        skills.add("product")
    return skills


@dataclass
class RoleGuidance:
    role: str
    title: str
    required_skills: list[str]
    recommended_modules: list[dict]      # all role modules, each with `completed` flag
    recommended_remaining: list[dict]    # completed == False
    already_completed: list[dict]        # completed == True
    skill_gaps: list[str]
    skill_gap_labels: list[str]
    matched_skills: list[str] = field(default_factory=list)
    skills_from_courses: list[str] = field(default_factory=list)


def guide_for_role(profile: UserProfile, role: TargetRole, matcher=None) -> RoleGuidance:
    data = _load()
    labels = data["skill_labels"]
    role_def = data["roles"][role.value]
    required = role_def["required_skills"]
    matcher = matcher or get_skill_matcher()

    from_courses = skills_from_completed(profile.completed_modules)
    have = {h.id for h in matcher.infer_user_skills(profile)} | from_courses
    gaps = [s for s in required if s not in have]
    matched = [s for s in required if s in have]

    done = {c.strip().upper() for c in profile.completed_modules}
    modules = _enrich_modules(role_def["recommended_modules"])
    for m in modules:
        m["completed"] = m["code"].upper() in done
    remaining = [m for m in modules if not m["completed"]]
    completed_mods = [m for m in modules if m["completed"]]

    return RoleGuidance(
        role=role.value,
        title=role_def["title"],
        required_skills=required,
        recommended_modules=modules,
        recommended_remaining=remaining,
        already_completed=completed_mods,
        skill_gaps=gaps,
        skill_gap_labels=[labels.get(s, s) for s in gaps],
        matched_skills=matched,
        skills_from_courses=sorted(from_courses & set(required)),
    )


def pick_primary_role(profile: UserProfile, slots: dict) -> TargetRole | None:
    """Choose which role to advise on: slot override, else first target role."""
    if slots.get("target_role"):
        try:
            return TargetRole(slots["target_role"])
        except ValueError:
            return None
    return profile.target_roles[0] if profile.target_roles else None


def skills_from_completed(completed: list[str]) -> set[str]:
    """Skills evidenced by completed modules (via module_skills.json)."""
    table = _load_module_skills()
    out: set[str] = set()
    for code in completed:
        out.update(table.get(code.strip().upper(), []))
    return out


def _known_module_codes() -> set[str]:
    """All codes we recognise: refreshed catalog union curated role-map modules."""
    codes = set(_load_catalog().keys())
    for role in _load()["roles"].values():
        codes.update(m["code"] for m in role["recommended_modules"])
    return codes


def unrecognized_completed(completed: list[str]) -> list[str]:
    """Completed codes not found in catalog union role-map (soft data-quality check)."""
    known = _known_module_codes()
    return [c for c in completed if c.strip().upper() not in known]


def guide_role_codes(role: TargetRole) -> list[dict]:
    """The role's curated module dicts (code/name) from role_module_map."""
    return _load()["roles"][role.value]["recommended_modules"]


def _role_name(role: TargetRole, code: str) -> str | None:
    for m in guide_role_codes(role):
        if m["code"] == code:
            return m.get("name")
    return None


def build_candidates(profile: UserProfile, role: TargetRole, matcher=None) -> list[dict]:
    """Deterministic candidate pool: curated role modules union gap-addressing modules,
    minus completed. Each annotated with skills / closes_gaps / prereq / source."""
    from .planner import prereq_satisfied  # local import avoids engine<->planner cycle

    g = guide_for_role(profile, role, matcher)
    gaps = set(g.skill_gaps)
    module_skills = _load_module_skills()
    catalog = _load_catalog()
    done = {c.strip().upper() for c in profile.completed_modules}

    role_codes = [m["code"] for m in guide_role_codes(role)]
    gap_codes = [
        code for code, tags in module_skills.items()
        if set(tags) & (set(g.required_skills) | gaps)
    ]
    ordered_codes: list[str] = []
    for code in [*role_codes, *gap_codes]:
        cu = code.upper()
        if cu in done or cu in {c.upper() for c in ordered_codes}:
            continue
        ordered_codes.append(code)

    out: list[dict] = []
    for code in ordered_codes:
        cat = catalog.get(code, {})
        skills = module_skills.get(code, [])
        tree = cat.get("prereq_tree")
        ok, missing = prereq_satisfied(tree, done)
        out.append({
            "code": code,
            "name": cat.get("name") or _role_name(role, code) or code,
            "credits": cat.get("credits"),
            "skills": skills,
            "closes_gaps": sorted(set(skills) & gaps),
            "prereq_ok": ok,
            "prereq_missing": missing,
            "verified": bool(cat),
            "source": "role" if code in set(role_codes) else "gap",
        })
    return out


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Deterministic fallback ranking: more gaps closed, role-curated first,
    fewer credits, then code (stable)."""
    return sorted(
        candidates,
        key=lambda c: (
            -len(c["closes_gaps"]),
            0 if c["source"] == "role" else 1,
            c["credits"] if isinstance(c.get("credits"), int) else 99,
            c["code"],
        ),
    )


_SELECT_SYSTEM = (
    "You help a Master's student choose modules for a target role from a FIXED "
    "candidate list. Rules: choose ONLY codes that appear in the list; never "
    "invent codes; prefer modules that close the student's skill gaps. Reply with "
    "one line 'SELECTED: <codes, comma-separated, best first>' then 1-2 plain "
    "sentences explaining the choice."
)


def _rule_rationale(selected: list[dict]) -> str:
    names = ", ".join(m["name"] for m in selected) or "(none)"
    return f"Recommended based on your skill gaps: {names}. (rule-based ranking)"


def _parse_selected_codes(raw: str) -> list[str]:
    m = _re.search(r"SELECTED\s*:\s*(.+)", raw or "", _re.IGNORECASE)
    if not m:
        return []
    line = m.group(1).splitlines()[0]
    return [tok.strip(" *.`").upper() for tok in _re.split(r"[,\s;]+", line) if tok.strip(" *.`")]


def select_modules(candidates: list[dict], gaps: list[str], n: int = 4,
                   personalized: bool = True) -> tuple[list[dict], str, str]:
    """Return (selected, rationale, source). source = 'llm' | 'rule'.

    Rules produce the candidate pool; the LLM may only pick codes from it
    (validated). Off/offline/invalid -> deterministic rank fallback.

    When `personalized` is False (consent opt-out), the LLM is NOT consulted at
    all — the student's gaps must not leave the system in the prompt — so we
    return the deterministic rule ranking."""
    ranked = rank_candidates(candidates)
    fallback = ranked[:n]
    if not candidates or not personalized or not llm.available():
        return fallback, _rule_rationale(fallback), "rule"

    listing = "\n".join(
        f"{c['code']} | {c['name']} | skills={','.join(c['skills'])} "
        f"| closes={','.join(c['closes_gaps'])}"
        for c in candidates
    )
    user = (
        f"Gaps to close: {', '.join(gaps) or 'none'}\n"
        f"Candidates:\n{listing}\nChoose up to {n}."
    )
    raw = llm.explain(_SELECT_SYSTEM, user, "")
    by_code = {c["code"].upper(): c for c in candidates}
    picked: list[dict] = []
    seen: set[str] = set()
    for code in _parse_selected_codes(raw):
        c = by_code.get(code)
        if c and code not in seen:
            picked.append(c)
            seen.add(code)
    if not picked:
        return fallback, _rule_rationale(fallback), "rule"
    # Strip the machine-readable SELECTED line so only the prose is shown to users.
    prose = _re.sub(r"(?im)^\s*SELECTED\s*:.*$", "", raw).strip() or _rule_rationale(picked)
    return picked[:n], prose, "llm"
