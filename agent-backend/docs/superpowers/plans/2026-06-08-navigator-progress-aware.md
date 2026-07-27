# Navigator Progress-Aware + LLM-Constrained Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade #7 Navigator from a fixed role→module table into a progress-aware, gap-driven engine where rules build a candidate pool and the LLM selects/ranks within it (validated, with deterministic fallback), plus completed-course awareness, a courses/career split, and a completed-code sanity warning.

**Architecture:** Rules build a candidate pool (curated role modules ∪ gap-addressing modules from a new `module_skills.json`, minus completed). The LLM picks an ordered shortlist *only from candidate codes*; output is validated (invented codes dropped) with a deterministic rank fallback when the LLM is off/offline/invalid. `completed_modules` feeds both skill inference (shrinks gaps) and candidate filtering.

**Tech Stack:** Python 3.11+, pydantic v2, pytest (LLM always mocked or fallback — offline-deterministic).

**Spec:** [docs/superpowers/specs/2026-06-08-navigator-progress-aware-design.md](../specs/2026-06-08-navigator-progress-aware-design.md)

---

## Notes for the implementer

- **Git repo.** Commit per task with the suggested message.
- **Run from project root** `E:\claude program\capstone_v2`: `python -m pytest tests/ -q`.
- **Offline invariant:** never call a real LLM in tests. Branch on `llm.available()`; tests either run the fallback path or monkeypatch `agents.navigator.engine.llm`.
- **Preserve `guide_for_role`** — it returns `skill_gaps`, which `eval.runner` checks (12/12). The new recommendation path layers on top. Don't change gap results for eval profiles (1/2/3/5): their `completed_modules` must not map to skills (the seed `module_skills.json` only covers role-map codes; eval profiles' completed codes like `BMD5301` are NOT in it → no change).
- **Ignore the docs-reminder hook** during code tasks — docs are Task 11.
- **File responsibilities:**
  - `data/module_skills.json` — curated module→skill map (powers gap inference + candidate pool).
  - `agents/navigator/engine.py` — skill inference from completed, candidate build, deterministic rank, LLM-constrained select+validate, unrecognized-code check.
  - `agents/navigator/planner.py` — graduation progress double-count guard.
  - `agents/navigator/agent.py` — `handle` (courses) + `career`, envelope.
  - `supervisor.py` — route `recommend_career_path`.

---

## Task 1: `data/module_skills.json` + loader

**Files:**
- Create: `data/module_skills.json`
- Modify: `agents/navigator/engine.py` (loader)
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Create `data/module_skills.json`** with the seed map (codes from `role_module_map.json`; tags from the 9-tag vocabulary):

```json
{
  "_comment": "人工编辑 模块代码->技能标签;标签须在 role_module_map.skill_labels(9个)内;独立于自动刷新的 module_catalog。",
  "modules": {
    "BMS5312": ["product", "finance"],
    "FT5001": ["product", "finance"],
    "FT5002": ["ai_ml", "finance", "data_analytics"],
    "IS5009": ["product", "programming"],
    "DBA5109": ["risk_modeling", "finance", "data_analytics"],
    "BMF5356": ["risk_modeling", "finance"],
    "BT4016": ["risk_modeling", "data_analytics"],
    "FT5010": ["programming", "risk_modeling", "data_analytics"],
    "FT5012": ["regulation", "security"],
    "BMF5355": ["finance", "regulation"],
    "FT5003": ["payments_systems", "security"],
    "FT5004": ["programming", "payments_systems"],
    "BMF5342": ["data_analytics", "finance"],
    "BMF5354": ["regulation", "finance"],
    "IS5008": ["security", "regulation"],
    "BT5153": ["ai_ml", "data_analytics", "programming"],
    "DBA5107": ["data_analytics", "finance"],
    "BMF5360": ["ai_ml", "data_analytics", "finance"],
    "FT5005": ["ai_ml", "programming", "finance"]
  }
}
```

- [ ] **Step 2: Write the failing test** — append to `tests/test_navigator.py`:

```python
# ---------- progress-aware: module_skills loader ----------
from agents.navigator.engine import _load_module_skills, _VALID_SKILL_TAGS


def test_module_skills_loads_and_tags_are_valid():
    m = _load_module_skills()
    assert m.get("BMS5312") == ["product", "finance"]
    # every tag in the file is within the controlled vocabulary
    for code, tags in m.items():
        assert set(tags) <= _VALID_SKILL_TAGS, code
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k module_skills -q`
Expected: FAIL — `cannot import name '_load_module_skills'`.

- [ ] **Step 4: Implement in `agents/navigator/engine.py`** — add near the path constants (`_MAP_PATH` etc.):

```python
_MODULE_SKILLS_PATH = _DATA_DIR / "module_skills.json"


def _valid_skill_tags() -> set[str]:
    return set(_load()["skill_labels"].keys())


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
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k module_skills -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/module_skills.json agents/navigator/engine.py tests/test_navigator.py
git commit -m "feat(#7): module_skills.json (module->skill) + loader"
```

---

## Task 2: `skills_from_completed` + `unrecognized_completed` (D + E)

**Files:**
- Modify: `agents/navigator/engine.py`
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_navigator.py`:

```python
# ---------- D: completed -> skills ; E: unrecognized codes ----------
from agents.navigator.engine import skills_from_completed, unrecognized_completed


def test_skills_from_completed_aggregates_valid_tags():
    s = skills_from_completed(["BMS5312", "FT5005"])
    assert {"product", "finance", "ai_ml", "programming"} <= s


def test_skills_from_completed_unknown_code_contributes_nothing():
    assert skills_from_completed(["NOPE999"]) == set()


def test_skills_from_completed_empty():
    assert skills_from_completed([]) == set()


def test_unrecognized_completed_flags_unknown_codes():
    # BMS5312 is a real role-map/catalog code; ZZZ000 is not.
    out = unrecognized_completed(["BMS5312", "ZZZ000"])
    assert "ZZZ000" in out and "BMS5312" not in out


def test_unrecognized_completed_empty():
    assert unrecognized_completed([]) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "skills_from_completed or unrecognized" -q`
Expected: FAIL — names not importable.

- [ ] **Step 3: Implement in `agents/navigator/engine.py`**:

```python
def skills_from_completed(completed: list[str]) -> set[str]:
    """Skills evidenced by completed modules (via module_skills.json)."""
    table = _load_module_skills()
    out: set[str] = set()
    for code in completed:
        out.update(table.get(code.strip().upper(), []))
    return out


def _known_module_codes() -> set[str]:
    """All codes we recognise: refreshed catalog ∪ curated role-map modules."""
    codes = set(_load_catalog().keys())
    for role in _load()["roles"].values():
        codes.update(m["code"] for m in role["recommended_modules"])
    return codes


def unrecognized_completed(completed: list[str]) -> list[str]:
    """Completed codes not found in catalog ∪ role-map (soft data-quality check)."""
    known = _known_module_codes()
    return [c for c in completed if c.strip().upper() not in known]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k "skills_from_completed or unrecognized" -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/engine.py tests/test_navigator.py
git commit -m "feat(#7): skills_from_completed (D) + unrecognized_completed (E)"
```

---

## Task 3: `guide_for_role` — completed-aware skills + flags (A + D)

**Files:**
- Modify: `agents/navigator/engine.py` (`RoleGuidance`, `guide_for_role`)
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_navigator.py`:

```python
# ---------- A + D: guide_for_role is completed-aware ----------
def test_guide_marks_completed_modules():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312"]  # a fintech_pm recommended module
    g = guide_for_role(p, TargetRole.fintech_pm)
    done = {m["code"] for m in g.recommended_modules if m.get("completed")}
    assert "BMS5312" in done
    assert "BMS5312" in {m["code"] for m in g.already_completed}
    assert "BMS5312" not in {m["code"] for m in g.recommended_remaining}


def test_guide_completed_shrinks_gap():
    # fintech_pm needs product; profile 1 lacks it. Completing BMS5312 (product)
    # should move product out of the gap.
    p = mock_data.get_profile("1")
    assert "product" in guide_for_role(p, TargetRole.fintech_pm).skill_gaps
    p.completed_modules = ["BMS5312"]  # product, finance
    g = guide_for_role(p, TargetRole.fintech_pm)
    assert "product" not in g.skill_gaps
    assert "product" in g.skills_from_courses
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "marks_completed or shrinks_gap" -q`
Expected: FAIL — `RoleGuidance` has no `already_completed` / `skills_from_courses`; gap still contains product.

- [ ] **Step 3: Implement in `agents/navigator/engine.py`**

Replace the `RoleGuidance` dataclass and `guide_for_role` with:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k "marks_completed or shrinks_gap" -q`
Expected: PASS.

- [ ] **Step 5: Run existing navigator tests + eval (regression)**

Run: `python -m pytest tests/test_navigator.py -q && python -m eval.runner`
Expected: existing tests still PASS (additive fields; profile 1 default has empty completed_modules so gaps unchanged); eval scorecard `12/12` (eval profiles' completed codes are not in module_skills).

- [ ] **Step 6: Commit**

```bash
git add agents/navigator/engine.py tests/test_navigator.py
git commit -m "feat(#7): guide_for_role marks completed + completed-aware gaps"
```

---

## Task 4: candidate pool + deterministic rank (F① + F④)

**Files:**
- Modify: `agents/navigator/engine.py`
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_navigator.py`:

```python
# ---------- F: candidate pool + deterministic ranking ----------
from agents.navigator.engine import build_candidates, rank_candidates


def test_candidates_exclude_completed_and_annotate():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312"]
    cands = build_candidates(p, TargetRole.fintech_pm)
    codes = {c["code"] for c in cands}
    assert "BMS5312" not in codes                       # completed excluded
    assert cands and all("closes_gaps" in c and "skills" in c for c in cands)


def test_candidates_include_gap_addressing_modules():
    # profile 1 lacks 'product' for fintech_pm; modules tagged 'product'
    # (BMS5312, FT5001, IS5009) should appear as candidates.
    p = mock_data.get_profile("1")
    codes = {c["code"] for c in build_candidates(p, TargetRole.fintech_pm)}
    assert {"FT5001", "IS5009"} & codes


def test_rank_prioritises_more_gaps_closed():
    p = mock_data.get_profile("1")
    cands = build_candidates(p, TargetRole.fintech_pm)
    ranked = rank_candidates(cands)
    closes = [len(c["closes_gaps"]) for c in ranked]
    assert closes == sorted(closes, reverse=True)       # non-increasing
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "candidates or rank_prioritises" -q`
Expected: FAIL — `build_candidates`/`rank_candidates` not importable.

- [ ] **Step 3: Implement in `agents/navigator/engine.py`**

> ⚠️ **Circular-import guard:** `planner.py` already does `from .engine import _load_catalog` at module top. Do NOT add `from .planner import ...` at engine's top level — import `prereq_satisfied` **locally inside `build_candidates`** (shown below).

```python
def build_candidates(profile: UserProfile, role: TargetRole, matcher=None) -> list[dict]:
    """Deterministic candidate pool: curated role modules ∪ gap-addressing modules,
    minus completed. Each annotated with skills / closes_gaps / prereq / source."""
    from .planner import prereq_satisfied  # local import avoids engine<->planner cycle

    g = guide_for_role(profile, role, matcher)
    gaps = set(g.skill_gaps)
    module_skills = _load_module_skills()
    catalog = _load_catalog()
    done = {c.strip().upper() for c in profile.completed_modules}

    # role-curated codes (always) + gap-addressing codes from module_skills
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


def guide_role_codes(role: TargetRole) -> list[dict]:
    """The role's curated module dicts (code/name) from role_module_map."""
    return _load()["roles"][role.value]["recommended_modules"]


def _role_name(role: TargetRole, code: str) -> str | None:
    for m in guide_role_codes(role):
        if m["code"] == code:
            return m.get("name")
    return None


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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k "candidates or rank_prioritises" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/engine.py tests/test_navigator.py
git commit -m "feat(#7): candidate pool + deterministic rank (F1/F4)"
```

---

## Task 5: LLM-constrained selector + validation (F② + F③)

**Files:**
- Modify: `agents/navigator/engine.py`
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_navigator.py`:

```python
# ---------- F: LLM-constrained selection with validation ----------
from agents.navigator import engine as nav_engine
from agents.navigator.engine import select_modules


def _cands(p=None):
    p = p or mock_data.get_profile("1")
    return build_candidates(p, TargetRole.fintech_pm)


def test_select_falls_back_to_rule_when_llm_off(monkeypatch):
    monkeypatch.setattr(nav_engine.llm, "available", lambda: False)
    cands = _cands()
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "rule"
    assert 1 <= len(selected) <= 3
    assert selected == rank_candidates(cands)[:3]


def test_select_llm_keeps_only_valid_codes(monkeypatch):
    cands = _cands()
    valid_code = cands[0]["code"]
    monkeypatch.setattr(nav_engine.llm, "available", lambda: True)
    monkeypatch.setattr(nav_engine.llm, "explain",
                        lambda *a, **k: f"SELECTED: {valid_code}, FAKE999\n因为它能补缺口。")
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "llm"
    codes = [c["code"] for c in selected]
    assert valid_code in codes and "FAKE999" not in codes


def test_select_all_invalid_falls_back(monkeypatch):
    cands = _cands()
    monkeypatch.setattr(nav_engine.llm, "available", lambda: True)
    monkeypatch.setattr(nav_engine.llm, "explain", lambda *a, **k: "SELECTED: FAKE1, FAKE2")
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "rule"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "select_" -q`
Expected: FAIL — `select_modules` not importable.

- [ ] **Step 3: Implement in `agents/navigator/engine.py`**

Add `from common import llm` to the imports at the top of the file. Then:

```python
import re as _re

_SELECT_SYSTEM = (
    "You help a Master's student choose modules for a target role from a FIXED "
    "candidate list. Rules: choose ONLY codes that appear in the list; never "
    "invent codes; prefer modules that close the student's skill gaps. Reply with "
    "one line 'SELECTED: <codes, comma-separated, best first>' then 1-2 plain "
    "sentences explaining the choice."
)


def _rule_rationale(selected: list[dict]) -> str:
    names = "、".join(m["name"] for m in selected) or "(无)"
    return f"按你的技能缺口优先推荐:{names}。(规则排序)"


def _parse_selected_codes(raw: str) -> list[str]:
    m = _re.search(r"SELECTED\s*:\s*(.+)", raw or "", _re.IGNORECASE)
    if not m:
        return []
    line = m.group(1).splitlines()[0]
    return [tok.strip().upper() for tok in _re.split(r"[,\s]+", line) if tok.strip()]


def select_modules(candidates: list[dict], gaps: list[str], n: int = 4
                   ) -> tuple[list[dict], str, str]:
    """Return (selected, rationale, source). source = 'llm' | 'rule'.

    Rules produce the candidate pool; the LLM may only pick codes from it
    (validated). Off/offline/invalid -> deterministic rank fallback."""
    ranked = rank_candidates(candidates)
    fallback = ranked[:n]
    if not candidates or not llm.available():
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k "select_" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/engine.py tests/test_navigator.py
git commit -m "feat(#7): LLM-constrained module selector + validation (F2/F3)"
```

---

## Task 6: planner graduation-progress double-count guard (B)

**Files:**
- Modify: `agents/navigator/planner.py` (`graduation_progress`)
- Test: `tests/test_navigator_planner.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_navigator_planner.py`:

```python
# ---------- B: progress never double-counts completed ----------
from agents.navigator.planner import graduation_progress


def test_graduation_progress_excludes_completed_from_planned():
    completed = ["BMS5312"]
    # even if a completed code sneaks into the recommended list, planned must not
    # count it again.
    prog = graduation_progress(completed, ["BMS5312", "FT5001"])
    only_remaining = graduation_progress(completed, ["FT5001"])
    assert prog["planned_credits"] == only_remaining["planned_credits"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator_planner.py -k excludes_completed -q`
Expected: FAIL — current `planned_credits` sums all recommended incl. the completed one.

- [ ] **Step 3: Implement in `agents/navigator/planner.py`** — in `graduation_progress`, change the planned sum to skip completed:

```python
    done = {c.strip().upper() for c in completed}
    completed_credits = sum(_credits(c, catalog) for c in completed)
    planned_credits = sum(
        _credits(c, catalog) for c in recommended_codes if c.strip().upper() not in done
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator_planner.py -k excludes_completed -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/planner.py tests/test_navigator_planner.py
git commit -m "fix(#7): graduation_progress never double-counts completed (B)"
```

---

## Task 7: `agent.handle` — courses via candidates→select→plan (A/B/E/F + envelope)

**Files:**
- Modify: `agents/navigator/agent.py`
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write/Update tests** — in `tests/test_navigator.py`:

REPLACE `test_handle_envelope` with:
```python
def test_handle_envelope():
    p = mock_data.get_profile("1")
    resp = handle(p, {})
    assert resp.status == "ok"
    assert resp.answer_type == "recommendation"
    assert resp.data["recommended"]                       # selected remaining modules
    assert resp.data["selection_source"] in ("llm", "rule")
    assert "graduation_progress" in resp.data and "study_plans" in resp.data
    assert "unrecognized_completed" in resp.data


def test_handle_excludes_completed_and_flags_unknown():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312", "ZZZ000"]
    resp = handle(p, {})
    rec_codes = {m["code"] for m in resp.data["recommended"]}
    assert "BMS5312" not in rec_codes                     # completed not recommended
    assert "BMS5312" in {m["code"] for m in resp.data["already_completed"]}
    assert "ZZZ000" in resp.data["unrecognized_completed"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "handle_envelope or excludes_completed_and_flags" -q`
Expected: FAIL — `data` has no `recommended`/`selection_source`/`unrecognized_completed`.

- [ ] **Step 3: Rewrite `agents/navigator/agent.py`** `handle` (keep the module docstring + `_SYSTEM`). Replace imports + `handle`:

```python
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse
from common.profile import UserProfile

from .engine import (
    build_candidates, guide_for_role, pick_primary_role, select_modules,
    unrecognized_completed,
)
from .planner import graduation_progress, prereq_warnings, what_if_pathways

_SYSTEM = (
    "You advise a Master's student on module choices for a target job role. "
    "Explain in 2-3 plain sentences why the selected modules fit and which gap "
    "to prioritise. Do not invent modules."
)


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    role = pick_primary_role(profile, slots)
    if role is None:
        return AgentResponse.needs(
            ["target_roles"],
            "请告诉我你的目标岗位(例如金融科技产品经理、量化风险等),我才能推荐合适的模块。",
        )

    g = guide_for_role(profile, role)
    personalized = profile.consent_flags.personalization
    skill_gaps_labels = g.skill_gap_labels if personalized else []

    candidates = build_candidates(profile, role)
    selected, rationale, source = select_modules(candidates, g.skill_gaps, n=4)
    selected_codes = [m["code"] for m in selected]

    warnings = [
        {"code": w.code, "missing": w.missing}
        for w in prereq_warnings(selected_codes, profile.completed_modules)
        if not w.satisfied
    ]
    progress = graduation_progress(profile.completed_modules, selected_codes)
    plans = what_if_pathways(selected_codes)
    unknown = unrecognized_completed(profile.completed_modules)

    module_names = "、".join(m["name"] for m in selected) or "(暂无可推荐模块)"
    gap_text = "、".join(skill_gaps_labels) if skill_gaps_labels else "无明显技能缺口"
    fallback = (
        f"针对「{g.title}」,建议优先选修:{module_names}。"
        f"你当前需要补强的方向:{gap_text}。"
    )
    if source == "llm":
        explanation = rationale  # LLM rationale already validated to candidate set
    else:
        explanation = llm.explain(_SYSTEM,
            f"Target role: {g.title}\nSelected modules: {module_names}\n"
            f"Skill gaps: {', '.join(skill_gaps_labels) or 'none'}",
            fallback,
        )
    speakable = explanation
    if warnings:
        speakable += f" 注意:有 {len(warnings)} 门模块的先修课你尚未修读。"
    if unknown:
        speakable += f" 另外:有 {len(unknown)} 个已修代码无法识别,请核对。"

    return AgentResponse(
        status="ok",
        answer_type="recommendation",
        speakable=speakable,
        data={
            "target_role": g.role,
            "recommended": selected,
            "already_completed": g.already_completed,
            "candidate_count": len(candidates),
            "skill_gaps": skill_gaps_labels,
            "personalized": personalized,
            "explanation": explanation,
            "selection_source": source,
            "prereq_warnings": warnings,
            "graduation_progress": progress,
            "study_plans": plans,
            "unrecognized_completed": unknown,
        },
        sources=["role_module_map", "module_skills", "module_catalog"],
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -q`
Expected: PASS (all navigator tests, incl. migrated envelope).

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/agent.py tests/test_navigator.py
git commit -m "feat(#7): handle uses candidate->select->plan; progress-aware envelope"
```

---

## Task 8: `agent.career` + supervisor routing (C)

**Files:**
- Modify: `agents/navigator/agent.py`, `supervisor.py`
- Test: `tests/test_navigator.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_navigator.py`:

```python
# ---------- C: career view + routing ----------
from agents.navigator.agent import career


def test_career_focuses_on_skills_not_scheduling():
    p = mock_data.get_profile("1")
    resp = career(p, {})
    assert resp.status == "ok"
    assert "required_skills" in resp.data and "gap_closing_modules" in resp.data
    assert "study_plans" not in resp.data            # career view drops scheduling


def test_supervisor_routes_career_path():
    from supervisor import route
    p = mock_data.get_profile("1")
    resp = route("recommend_career_path", p, {})
    assert resp.status == "ok"
    assert "gap_closing_modules" in resp.data        # came from career(), not handle()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_navigator.py -k "career_focuses or routes_career" -q`
Expected: FAIL — `career` not importable; route still points at `handle` (no `gap_closing_modules`).

- [ ] **Step 3: Implement**

In `agents/navigator/agent.py`, add after `handle`:
```python
_CAREER_SYSTEM = (
    "You give a Master's student career-path guidance for a target role. In 2-3 "
    "plain sentences: name the role's key skills, what they already have, the gap "
    "to prioritise, and which modules help close it. Do not invent modules."
)


def career(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    role = pick_primary_role(profile, slots)
    if role is None:
        return AgentResponse.needs(
            ["target_roles"],
            "请告诉我你的目标岗位,我才能给出职业路径与技能建议。",
        )

    g = guide_for_role(profile, role)
    personalized = profile.consent_flags.personalization
    gap_labels = g.skill_gap_labels if personalized else []

    candidates = build_candidates(profile, role)
    gap_closing = [c for c in candidates if c["closes_gaps"]]
    selected, rationale, source = select_modules(gap_closing or candidates, g.skill_gaps, n=4)
    unknown = unrecognized_completed(profile.completed_modules)

    names = "、".join(m["name"] for m in selected) or "(暂无)"
    gap_text = "、".join(gap_labels) if gap_labels else "无明显技能缺口"
    fallback = (
        f"目标「{g.title}」的关键技能:{ '、'.join(g.required_skills) }。"
        f"你需优先补强:{gap_text};可通过选修 {names} 来补足。"
    )
    explanation = rationale if source == "llm" else llm.explain(
        _CAREER_SYSTEM,
        f"Role: {g.title}\nRequired: {', '.join(g.required_skills)}\n"
        f"Has: {', '.join(g.matched_skills) or 'few'}\nGaps: {', '.join(gap_labels) or 'none'}\n"
        f"Gap-closing modules: {names}",
        fallback,
    )

    return AgentResponse(
        status="ok",
        answer_type="recommendation",
        speakable=explanation,
        data={
            "target_role": g.role,
            "required_skills": g.required_skills,
            "matched_skills": g.matched_skills,
            "skills_from_courses": g.skills_from_courses,
            "skill_gaps": gap_labels,
            "gap_closing_modules": selected,
            "personalized": personalized,
            "explanation": explanation,
            "selection_source": source,
            "unrecognized_completed": unknown,
        },
        sources=["role_module_map", "module_skills"],
    )
```

In `supervisor.py`, change the `_ROUTES` entry:
```python
    "recommend_career_path": ("agents.navigator.agent", "career"),
```
(from the current `("agents.navigator.agent", "handle")`).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_navigator.py -k "career_focuses or routes_career" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/navigator/agent.py supervisor.py tests/test_navigator.py
git commit -m "feat(#7): career handler (skills-focused) + route recommend_career_path"
```

---

## Task 9: demo data — current-student profile

**Files:**
- Modify: `common/mock_data.py`
- Test: none new (verify suite + a smoke)

- [ ] **Step 1: Add a current-student profile `"6"`** to `_PROFILES` in `common/mock_data.py`. Mirror the structure of profile `"5"` but with `lifecycle_stage=LifecycleStage.current`, target role `fintech_pm`, and:
```python
        completed_modules=["BMS5312", "FT5001", "ZZZ000"],  # 2 real fintech_pm modules + 1 typo (demo E)
```
Give it a valid `application=None` (current students may have no application) or reuse a minimal one; set `consent_flags=ConsentFlags(personalization=True, reminders=True)`. Keep all enum fields valid. Do NOT modify profiles 1–5 (eval depends on them).

- [ ] **Step 2: Verify**

Run:
```bash
python -m pytest tests/ -q
python run.py courses --profile 6
python run.py career --profile 6
```
Expected: suite PASS; `courses` shows recommended (excluding BMS5312/FT5001), an `unrecognized_completed` mention of ZZZ000, `selection_source=rule` (no key); `career` shows skills/gap-closing without study plans. No traceback.

- [ ] **Step 3: Commit**

```bash
git add common/mock_data.py
git commit -m "feat(#7): current-student demo profile (completed overlap + typo)"
```

---

## Task 10: student results template (#7 render)

**Files:**
- Modify: `student/templates/results.html`
- Test: `tests/test_student.py` (adjust only if it asserts old `recommended_modules`)

- [ ] **Step 1: Check the student test** — Run: `python -m pytest tests/test_student.py -q`. If a test asserts `recommendation` data keys, note them; the navigator data is now under `recommended` / `gap_closing_modules`. Update any such assertion to the new keys.

- [ ] **Step 2: Update the `#7` section of `student/templates/results.html`**. Read the file to find the recommendation block (it renders `r.recommendation`). Replace the module list rendering to iterate `m.data["recommended"]` with each module showing name + `closes_gaps` + `completed`/`verified`, and add: a "已修✓" list from `m.data["already_completed"]`, a soft warning when `m.data["unrecognized_completed"]` is non-empty ("以下已修代码未找到,请核对：…"), and a small note showing `m.data["selection_source"]` ("由 AI 在候选内挑选" vs "规则排序"). Keep existing styling/classes. Use this block shape (adapt to the file's existing markup):

```html
{% if r.recommendation is defined %}
{% set rc = r.recommendation %}
{% if rc.status == "ok" %}
  <p style="margin-top:0">{{ rc.data["explanation"] }}</p>
  <div class="note"><span class="why">推荐方式：{{ '由 AI 在候选内挑选' if rc.data["selection_source"] == 'llm' else '规则排序(未配 AI)' }}</span></div>
  <h3>建议选修(待修)</h3>
  <ul>
    {% for m in rc.data["recommended"] %}
    <li><strong>{{ m.code }}</strong> {{ m.name }}
      {% if m.closes_gaps %}<span class="why">— 补:{{ m.closes_gaps|join('、') }}</span>{% endif %}
      {% if not m.verified %}<span class="why">(目录未收录)</span>{% endif %}</li>
    {% endfor %}
  </ul>
  {% if rc.data["already_completed"] %}
  <p class="why">已修 ✓：{% for m in rc.data["already_completed"] %}{{ m.code }}{% if not loop.last %}、{% endif %}{% endfor %}</p>
  {% endif %}
  {% if rc.data["unrecognized_completed"] %}
  <div class="note note--info">以下已修代码未在课程库中找到(可能拼写有误或暂未收录),请核对：{{ rc.data["unrecognized_completed"]|join('、') }}</div>
  {% endif %}
{% endif %}
{% endif %}
```
(If the template currently relies on `study_plans`/`graduation_progress` rendering, keep those blocks but point them at the new keys — they still exist in `handle`'s data.)

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/test_student.py -q` → PASS. Also `python -c "from student.webapp import app; print('ok')"` → `ok`.

- [ ] **Step 4: Commit**

```bash
git add student/templates/results.html tests/test_student.py
git commit -m "feat(#7): student results render recommended/completed/unknown (progress-aware)"
```

---

## Task 11: docs (contract / design / changelog / overview)

**Files:**
- Modify: `docs/02-interface-contracts.md`, `docs/10-navigator-v2-design.md`, `CHANGELOG.md`, `docs/00-project-overview.md`

- [ ] **Step 1: Update contract `docs/02-interface-contracts.md §4 #7`** — replace the `#7` data block with the two-intent v3 shape (courses: `recommended`/`already_completed`/`graduation_progress`/`study_plans`/`unrecognized_completed`/`selection_source`; career: `required_skills`/`matched_skills`/`gap_closing_modules`/`selection_source`), and add a note: "推荐为规则候选池 → LLM 受约束挑选(只在候选内,经校验)→ 无 key/离线走规则兜底(`selection_source`);永不输出不存在的模块。"

- [ ] **Step 2: Add a v3 note to the top of `docs/10-navigator-v2-design.md`**:
```markdown
> **v3 起(2026-06-08)进度感知 + LLM 受约束选课**:推荐改为「规则候选池(岗位课 ∪ 按缺口纳入,排除已修)→ LLM 在候选内挑选/排序+校验 → 确定性兜底」;新增 `module_skills.json`(已修→技能、缺口→候选,一份两用);区分 `recommend_courses`/`recommend_career_path`;已修代码软校验。见 [v3 spec](superpowers/specs/2026-06-08-navigator-progress-aware-design.md) 与 [plan](superpowers/plans/2026-06-08-navigator-progress-aware.md)。
```

- [ ] **Step 3: Prepend a CHANGELOG entry** under `## [Unreleased]`:
```markdown
### 2026-06-08 (6)
- **#7 · Navigator 进度感知 + LLM 受约束选课(已落地)**:新增 `data/module_skills.json`(模块→技能,一份两用);`guide_for_role` 用已修课程缩小技能缺口(D)+ 标注已修(A);`build_candidates`(岗位课 ∪ 按缺口纳入,排除已修)+ `rank_candidates`(确定性)+ `select_modules`(LLM 只在候选内挑选/排序,编造代码丢弃,无 key/离线走规则兜底,`selection_source` 透出)(F);`graduation_progress` 不重复计已修、课表只排待修(B);新增 `career` handler + supervisor 路由 `recommend_career_path`(C);已修代码软校验提醒 `unrecognized_completed`(E);新增在读学生 demo profile 6;学生页渲染待修/已修/未识别。永不输出不存在的模块;离线确定性。全套测试通过;eval.runner 12/12。
```

- [ ] **Step 4: Update `docs/00-project-overview.md` §4 #7 row** to mention progress-aware + LLM-constrained selection + courses/career split.

- [ ] **Step 5: Commit**

```bash
git add docs/ CHANGELOG.md
git commit -m "docs(#7): document progress-aware navigator + LLM-constrained selection"
```

---

## Task 12: Final verification

- [ ] **Step 1: Full suite** — `python -m pytest tests/ -q` — Expected: all PASS (baseline 247 +1 skipped; this adds ~22 tests).
- [ ] **Step 2: Eval regression** — `python -m eval.runner` — Expected: `12/12` (navigator gaps unchanged for profiles 1/2/3/5).
- [ ] **Step 3: CLI smokes** — `python run.py courses --profile 6` and `python run.py career --profile 6` — Expected: distinct outputs; courses excludes completed + flags ZZZ000 + `selection_source=rule`; career shows skills/gap-closing, no study plans. No traceback.
- [ ] **Step 4: JSON validity** — `python -c "import json; json.load(open('data/module_skills.json',encoding='utf-8')); print('ok')"` — Expected: `ok`.
- [ ] **Step 5: (Optional) real LLM smoke** — if a DeepSeek key is configured, `python run.py courses --profile 6` should show `selection_source=llm` and only candidate-set modules. Skip if no key.
