# Comparator v3 (Fact/Synthesis Separation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make #6 Comparator expose the PDF-required 8 comparison dimensions and a structurally-enforced fact↔synthesis boundary, with a deterministic anti-ranking guard — without numerically scoring subjective dimensions.

**Architecture:** Each comparison cell becomes a three-state `FactCell` (`verified`/`unknown`/`synthesis`). The engine returns each row split into `facts` (sourced cells) and `synthesis` (the 3 derived fit signals). Numeric scoring consumes **only** `verified` cells. The agent envelope splits `data` into `facts_table` and `synthesis` zones; the LLM narrative passes a deterministic `violates_ranking` guard or falls back to a safe template.

**Tech Stack:** Python 3.11+, pydantic (schema), pytest. Offline-deterministic; LLM optional.

**Spec:** [docs/superpowers/specs/2026-06-08-comparator-fact-synthesis-design.md](../specs/2026-06-08-comparator-fact-synthesis-design.md)

---

## Notes for the implementer

- **Not a git repo.** Each task ends with a **Checkpoint** (run the suite) instead of a commit. If you want history, run `git init` first and commit at each checkpoint with the suggested message.
- **Run tests from project root** `E:\claude program\capstone_v2`: `python -m pytest tests/ -q`.
- **Intentional contract change.** The row/envelope shape changes from v2. The existing `tests/test_comparator.py` and one test in `tests/test_consent_gate.py` are **migrated** to the new shape as part of this plan (Tasks 6–7). `eval.runner` cases are checklist+navigator only (no comparator), so its `12/12` is unaffected — verify it stays green at the end.
- **File responsibilities:**
  - `agents/comparator/engine.py` — data load + normalization, scoring, derivation, `violates_ranking`, `compare()` returning facts/synthesis.
  - `agents/comparator/agent.py` — envelope two-zone assembly + narrative guard + consent gate.
  - `admin/schemas.py` — `ProgramEntry.values` accepts three-state cells (shared by refresh + admin).
  - `data/programs_dataset.json` — 4 new dimensions + three-state cells.
  - `student/templates/results.html` — render facts table (per-cell kind/source) + separate AI-synthesis block.
  - docs: `02-interface-contracts.md`, `09-comparator-v2-design.md`, `00-project-overview.md`, `CHANGELOG.md`.

---

## Task 1: `FactCell` type + cell normalization (engine)

**Files:**
- Modify: `agents/comparator/engine.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: three-state cell normalization ----------
from agents.comparator.engine import FactCell, _normalize_cell, _verified_text


def test_normalize_bare_string_is_verified_with_row_source():
    cell = _normalize_cell("S$74,120", "http://x", "2026-06-05")
    assert cell == FactCell(text="S$74,120", kind="verified",
                            source_url="http://x", fetched_at="2026-06-05")


def test_normalize_object_synthesis_drops_inherited_source():
    cell = _normalize_cell({"text": "深度高", "kind": "synthesis"}, "http://x", "2026-06-05")
    assert cell.kind == "synthesis"
    assert cell.source_url is None and cell.fetched_at is None


def test_normalize_object_unknown_kind_preserved():
    cell = _normalize_cell({"text": "未公开", "kind": "unknown"}, "http://x", "2026-06-05")
    assert cell.kind == "unknown" and cell.text == "未公开"


def test_normalize_object_bad_kind_falls_back_to_verified():
    cell = _normalize_cell({"text": "x", "kind": "bogus"}, "http://x", "2026-06-05")
    assert cell.kind == "verified"


def test_verified_text_only_returns_verified():
    facts = {
        "fees": FactCell("S$1", "verified", "u", "d"),
        "intake": FactCell("未公开", "unknown"),
        "technical_depth": FactCell("高", "synthesis"),
    }
    assert _verified_text(facts, "fees") == "S$1"
    assert _verified_text(facts, "intake") is None
    assert _verified_text(facts, "technical_depth") is None
    assert _verified_text(facts, "missing") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py -k "normalize or verified_text" -q`
Expected: FAIL — `cannot import name 'FactCell'`.

- [ ] **Step 3: Implement in `agents/comparator/engine.py`**

Add near the top constants (after `_CRITERIA`):

```python
# Cell provenance kinds (spec §2.1). verified -> sourced fact; unknown -> not
# published; synthesis -> editorial/AI interpretation (never scored).
_VERIFIED, _UNKNOWN, _SYNTHESIS = "verified", "unknown", "synthesis"
_CELL_KINDS = {_VERIFIED, _UNKNOWN, _SYNTHESIS}
```

Add dataclass (after the imports / near `ComparisonRow`, but it must be defined before use):

```python
@dataclass(frozen=True)
class FactCell:
    text: str
    kind: str  # verified | unknown | synthesis
    source_url: str | None = None
    fetched_at: str | None = None


def _normalize_cell(raw, row_src: str | None, row_fetched: str | None) -> FactCell:
    """Normalize a raw cell (bare string OR object) into a FactCell.

    Bare string -> verified, inheriting the row-level source. An object's source
    is inherited only for verified cells (unknown/synthesis carry no provenance).
    """
    if isinstance(raw, dict):
        kind = raw.get("kind", _VERIFIED)
        if kind not in _CELL_KINDS:
            kind = _VERIFIED
        verified = kind == _VERIFIED
        return FactCell(
            text=str(raw.get("text", "")),
            kind=kind,
            source_url=raw.get("source_url", row_src if verified else None),
            fetched_at=raw.get("fetched_at", row_fetched if verified else None),
        )
    return FactCell(text=str(raw), kind=_VERIFIED, source_url=row_src, fetched_at=row_fetched)


def _row_facts(p: dict) -> dict[str, FactCell]:
    src, fetched = p.get("source_url"), p.get("fetched_at")
    return {dim: _normalize_cell(raw, src, fetched) for dim, raw in p.get("values", {}).items()}


def _verified_text(facts: dict[str, FactCell], dim: str) -> str | None:
    cell = facts.get(dim)
    return cell.text if (cell is not None and cell.kind == _VERIFIED) else None
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py -k "normalize or verified_text" -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/test_comparator.py -q`
Expected: import errors only from later-task tests not yet added are NOT present; existing v2 tests still pass (engine unchanged behaviorally so far). Suggested commit msg: `feat(#6): add three-state FactCell normalization`.

---

## Task 2: `violates_ranking` deterministic guard (engine)

**Files:**
- Modify: `agents/comparator/engine.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: anti-ranking guard ----------
from agents.comparator.engine import violates_ranking


def test_ranking_phrases_are_flagged():
    for bad in [
        "NUS 优于 NTU", "这个项目更好", "综合排名第一", "NUS is better than SMU",
        "the best programme for fintech", "NTU outperforms HKUST", "ranked top",
    ]:
        assert violates_ranking(bad), bad


def test_fit_language_is_allowed():
    for ok in [
        "结合你的目标,NUS 在支付方向更契合你", "best fit for your goals",
        "最适合你的目标的是 NUS DFT", "各项目各有侧重,建议按目标权衡。",
    ]:
        assert not violates_ranking(ok), ok
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py -k ranking -q`
Expected: FAIL — `cannot import name 'violates_ranking'`.

- [ ] **Step 3: Implement in `agents/comparator/engine.py`**

```python
# Cross-programme ranking phrases the narrative must never produce (spec §4).
# Deliberately conservative: a false positive only forces the safe fallback.
# "best fit / 最适合你 / 更契合" are fit-to-goal phrasing and are NOT banned.
_RANKING_PATTERNS = [
    r"优于", r"更好", r"胜过", r"排名", r"第一名", r"最好的(?:项目|选择|课程|学校)",
    r"\bbetter than\b", r"\bbest (?:program|programme|option|choice|school)\b",
    r"\boutperform", r"\bsuperior to\b", r"#1\b", r"\branked\b",
    r"\btop (?:program|programme)\b",
]


def violates_ranking(text: str) -> bool:
    """True if `text` contains a cross-programme ranking claim."""
    t = (text or "").lower()
    return any(re.search(p, t) for p in _RANKING_PATTERNS)
```

(`re` is already imported at the top of engine.py.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py -k ranking -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/test_comparator.py -q`
Expected: no regressions. Suggested commit msg: `feat(#6): add deterministic anti-ranking guard`.

---

## Task 3: Schema accepts three-state cells (admin/refresh)

**Files:**
- Modify: `admin/schemas.py:131-136` (`ProgramEntry`)
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: schema accepts three-state cells ----------
from admin.schemas import ProgramsDataset, validate_draft


def _min_dataset(values):
    return {
        "dimensions": list(values.keys()),
        "disclaimer": "对比基于公开整理数据,不构成排名。",
        "programs": [{
            "program": "X", "is_target": True,
            "source_url": "http://x", "fetched_at": "2026-06-05",
            "values": values,
        }],
    }


def test_schema_accepts_bare_string_and_cell_objects():
    draft = _min_dataset({
        "fees": "S$1",
        "intake": {"text": "未公开", "kind": "unknown"},
        "technical_depth": {"text": "高", "kind": "synthesis"},
    })
    ok, err = validate_draft(ProgramsDataset, draft)
    assert ok, err


def test_schema_rejects_bad_kind():
    draft = _min_dataset({"fees": {"text": "x", "kind": "bogus"}})
    ok, err = validate_draft(ProgramsDataset, draft)
    assert not ok
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py -k schema -q`
Expected: FAIL — current `values: dict[str, str]` rejects the object cells.

- [ ] **Step 3: Implement in `admin/schemas.py`**

Add `Literal` to the typing import at the top of the file (find the existing `from typing import ...`; if none, add `from typing import Literal`). Then add a cell model and update `ProgramEntry`:

```python
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
    role_strengths: list[str] = Field(default_factory=list)
```

The existing `_values_cover_dimensions` validator is unchanged (it checks `set(self.dimensions) - set(p.values)`, which still works on keys).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py -k schema -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/test_admin.py tests/test_admin_extended.py tests/test_refresh.py -q`
Expected: PASS (schema change is additive; bare strings still validate). Suggested commit msg: `feat(#6): schema accepts three-state comparison cells`.

---

## Task 4: Data — add 4 dimensions + three-state cells

**Files:**
- Modify: `data/programs_dataset.json`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: dataset has 11 dims incl 4 new, validates, has 3 kinds ----------
import json as _json
from pathlib import Path as _Path


def test_dataset_has_new_dimensions_and_validates():
    raw = _json.loads((_Path("data") / "programs_dataset.json").read_text(encoding="utf-8"))
    dims = set(raw["dimensions"])
    assert {"typical_profile", "industry_orientation",
            "technical_depth", "career_pathways"} <= dims
    ok, err = validate_draft(ProgramsDataset, raw)
    assert ok, err


def test_dataset_exercises_all_three_kinds():
    comp = compare([TargetRole.fintech_pm])
    kinds = {c.kind for r in comp.rows for c in r.facts.values()}
    assert kinds == {"verified", "unknown", "synthesis"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py -k "new_dimensions or three_kinds" -q`
Expected: FAIL — dims missing; only `verified` kind present.

- [ ] **Step 3: Edit `data/programs_dataset.json`**

(a) Replace the `dimensions` array with (append the 4 new dims):

```json
  "dimensions": [
    "curriculum_focus", "duration", "format", "fees", "intake", "scholarship",
    "gmat_gre", "typical_profile", "industry_orientation", "technical_depth",
    "career_pathways"
  ],
```

(b) For **every** programme, add these 4 keys inside its `values` object (synthesis cells). Use the per-programme text below.

NUS:
```json
        "typical_profile": {"text": "适合 CS/工程或量化背景、想进入金融科技的申请人;GRE/GMAT 非强制。", "kind": "synthesis"},
        "industry_orientation": {"text": "含两学期 FT5007 capstone,可做产业链接/实习型项目。", "kind": "synthesis"},
        "technical_depth": {"text": "技术深度高:计算技术 + 金融数据分析与智能 + 数字金融交易与风险三方向。", "kind": "synthesis"},
        "career_pathways": {"text": "AI 软件开发、数据科学家、FinTech 安全专家、金融量化分析师。", "kind": "synthesis"}
```
SMU Applied Finance:
```json
        "typical_profile": {"text": "面向金融/商科背景、想做应用金融与金融科技的申请人。", "kind": "synthesis"},
        "industry_orientation": {"text": "通过 SMU 合作网络提供实习选项,偏应用金融导向。", "kind": "synthesis"},
        "technical_depth": {"text": "技术深度中等:以应用金融为主,金融科技为选修方向。", "kind": "synthesis"},
        "career_pathways": {"text": "应用金融、金融市场、金融科技相关岗位。", "kind": "synthesis"}
```
NTU:
```json
        "typical_profile": {"text": "面向数据科学/AI/IT 背景、偏好密集授课的申请人;偏好两年相关经验但非必需。", "kind": "synthesis"},
        "industry_orientation": {"text": "侧重金融自动化与数字金融服务,产业应用导向强。", "kind": "synthesis"},
        "technical_depth": {"text": "技术深度高:数据科学、AI、区块链/密码学。", "kind": "synthesis"},
        "career_pathways": {"text": "智能流程自动化、数字金融服务、区块链相关岗位。", "kind": "synthesis"}
```
SMU MITB:
```json
        "typical_profile": {"text": "面向 IT/商业/数据背景、想做金融科技与分析的申请人。", "kind": "synthesis"},
        "industry_orientation": {"text": "聚焦业务与金融应用的数据/流程/技术管理,产业导向中等。", "kind": "synthesis"},
        "technical_depth": {"text": "技术深度中等偏数据:数据、流程、技术与管理策略。", "kind": "synthesis"},
        "career_pathways": {"text": "金融科技与分析、数据分析、业务技术管理岗位。", "kind": "synthesis"}
```
HKUST:
```json
        "typical_profile": {"text": "跨工程/商业/科学背景的申请人;GMAT/GRE 要求官方页未明确。", "kind": "synthesis"},
        "industry_orientation": {"text": "跨学科金融科技,覆盖区块链/数据科学/决策分析,产业导向强。", "kind": "synthesis"},
        "technical_depth": {"text": "技术深度高:IT、区块链、数据科学、机器学习、决策分析。", "kind": "synthesis"},
        "career_pathways": {"text": "金融科技工程、数据科学、区块链、决策分析岗位。", "kind": "synthesis"}
```

(c) Convert NTU's **unavailable** cells from bare strings to `unknown` objects:
```json
        "fees": {"text": "官方对比页未给出稳定学费数字,请以 NTU 官方学费页为准。", "kind": "unknown"},
        "intake": {"text": "请见 NTU 官方页确认当前 intake 与截止日期。", "kind": "unknown"},
        "scholarship": {"text": "请见 NTU 官方奖学金/财务页。", "kind": "unknown"},
```

(d) Convert HKUST's `gmat_gre` to `unknown`:
```json
        "gmat_gre": {"text": "官方对比页未明确说明,请查 HKUST 录取要求。", "kind": "unknown"},
```

JSON hygiene: the last key in each `values` object must NOT have a trailing comma; keys before it must. After editing, the file must remain valid JSON.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py -k "new_dimensions or three_kinds" -q`
Expected: PASS. Also `python -c "import json; json.load(open('data/programs_dataset.json',encoding='utf-8'))"` exits 0.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/test_comparator.py -k "new_dimensions or three_kinds or schema" -q`
Expected: PASS. Suggested commit msg: `feat(#6): add 4 PDF dimensions + three-state cells to dataset`.

---

## Task 5: Scoring consumes only verified cells (engine `compare`)

**Files:**
- Modify: `agents/comparator/engine.py` (`ComparisonRow`, add `RowSynthesis`, rewrite `compare`)
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: scoring reads only verified; facts/synthesis split ----------
from agents.comparator.engine import RowSynthesis


def test_row_has_facts_and_synthesis_split():
    comp = compare([TargetRole.fintech_pm])
    r = comp.rows[0]
    assert isinstance(r.facts, dict) and isinstance(r.facts["fees"], FactCell)
    assert isinstance(r.synthesis, RowSynthesis)
    assert set(r.synthesis.score_breakdown) == {"role_fit", "cost", "duration"}


def test_unknown_fee_scores_neutral_cost():
    # NTU's fee cell is unknown -> cost must be the neutral 0.5, never parsed.
    comp = compare([TargetRole.fintech_pm])
    ntu = next(r for r in comp.rows if r.program.startswith("NTU"))
    assert ntu.facts["fees"].kind == "unknown"
    assert ntu.synthesis.score_breakdown["cost"] == 0.5


def test_synthesis_cells_never_affect_role_fit():
    # technical_depth (synthesis) mentions 区块链-like words but must not feed role_fit.
    comp = compare([TargetRole.payments])
    for r in comp.rows:
        # role derivation runs on verified curriculum_focus only
        derived, _ = derive_role_strengths(_verified_text(r.facts, "curriculum_focus") or "")
        assert set(r.synthesis.matched_roles) <= set(derived)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py -k "facts_and_synthesis or unknown_fee or synthesis_cells" -q`
Expected: FAIL — `cannot import name 'RowSynthesis'`; `ComparisonRow` has no `.facts`.

- [ ] **Step 3: Implement in `agents/comparator/engine.py`**

Replace the `ComparisonRow` dataclass with:

```python
@dataclass
class RowSynthesis:
    matched_roles: list[str]
    role_reasons: dict[str, list[str]]
    weighted_score: float
    score_breakdown: dict[str, float]


@dataclass
class ComparisonRow:
    program: str
    is_target: bool
    facts: dict[str, FactCell]
    synthesis: RowSynthesis
    source_url: str | None = None   # row-level default provenance
    fetched_at: str | None = None
```

Replace the body of `compare(...)` (keep the signature) with:

```python
def compare(target_roles: list[TargetRole],
            priorities: dict[str, float] | None = None) -> Comparison:
    data = _load()
    role_values = {r.value for r in target_roles}
    weights = _normalise_weights(priorities)
    progs = data["programs"]
    facts_by_prog = {p["program"]: _row_facts(p) for p in progs}

    # Per-criterion raw values come from VERIFIED cells only; unknown/synthesis
    # -> None -> neutral 0.5 (via _inverse_minmax). Subjective cells never scored.
    fee_raw = {p["program"]: parse_fee_sgd(_verified_text(facts_by_prog[p["program"]], "fees") or "")
               for p in progs}
    dur_raw = {p["program"]: parse_min_months(_verified_text(facts_by_prog[p["program"]], "duration") or "")
               for p in progs}
    cost_score = _inverse_minmax(fee_raw)
    dur_score = _inverse_minmax(dur_raw)

    rows: list[ComparisonRow] = []
    for p in progs:
        name = p["program"]
        facts = facts_by_prog[name]
        roles, reasons = derive_role_strengths(_verified_text(facts, "curriculum_focus") or "")
        matched = sorted(role_values & set(roles))
        role_fit = (len(matched) / len(role_values)) if role_values else 0.0
        breakdown = {
            "role_fit": role_fit,
            "cost": cost_score[name],
            "duration": dur_score[name],
        }
        weighted = sum(weights[k] * breakdown[k] for k in weights)
        rows.append(ComparisonRow(
            program=name, is_target=p.get("is_target", False),
            facts=facts,
            synthesis=RowSynthesis(
                matched_roles=matched,
                role_reasons={r: reasons[r] for r in matched},
                weighted_score=round(weighted, 4),
                score_breakdown=breakdown,
            ),
            source_url=p.get("source_url"), fetched_at=p.get("fetched_at"),
        ))

    best = None
    if rows:
        best_row = max(rows, key=lambda r: (r.synthesis.weighted_score, r.is_target))
        if best_row.synthesis.weighted_score > 0:
            best = best_row.program

    return Comparison(
        dimensions=data["dimensions"], rows=rows, disclaimer=data["disclaimer"],
        best_for_you=best, weights=weights,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py -k "facts_and_synthesis or unknown_fee or synthesis_cells" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Migrate the v2 engine-level tests still on the old shape**

In `tests/test_comparator.py`, update these existing tests:

`test_five_real_programs_seven_dimensions` → rename + retarget:
```python
def test_eleven_dimensions_incl_new_and_legacy():
    comp = compare([TargetRole.fintech_pm])
    assert {r.program for r in comp.rows} == PROGRAMS
    assert len(comp.dimensions) == 11
    assert {"intake", "scholarship", "gmat_gre",
            "typical_profile", "industry_orientation",
            "technical_depth", "career_pathways"} <= set(comp.dimensions)
```

`test_matched_roles_intersect_target_with_reasons` → use `.synthesis`:
```python
def test_matched_roles_intersect_target_with_reasons():
    comp = compare([TargetRole.quant_risk])
    nus = next(r for r in comp.rows if r.program.startswith("NUS"))
    assert "quant_risk" in nus.synthesis.matched_roles
    assert nus.synthesis.role_reasons["quant_risk"]
```

`test_cost_priority_changes_best_fit` → use `.synthesis` + verified fee text:
```python
def test_cost_priority_changes_best_fit():
    comp = compare([TargetRole.fintech_pm], {"cost": 0.9, "role_fit": 0.1})
    best = max(comp.rows, key=lambda r: r.synthesis.weighted_score)
    assert best.synthesis.weighted_score == comp.rows[0].synthesis.weighted_score \
        or best.program == comp.best_for_you
    cheapest = min(
        (r for r in comp.rows if _verified_text(r.facts, "fees") is not None),
        key=lambda r: parse_fee_sgd(_verified_text(r.facts, "fees")) or 1e9,
    )
    assert cheapest.synthesis.score_breakdown["cost"] == 1.0
```

(`test_rows_carry_provenance`, `test_default_weight_is_role_fit`, `test_weights_normalised`, `test_target_wins_ties`, derivation + parse tests are unchanged and stay.)

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest tests/test_comparator.py -q`
Expected: all engine-level tests PASS; only the `handle`-level tests (Task 7) may still fail. Suggested commit msg: `feat(#6): compare() returns facts/synthesis; score only verified`.

---

## Task 6: Agent envelope two zones + narrative guard + consent gate

**Files:**
- Modify: `agents/comparator/agent.py`
- Test: `tests/test_comparator.py`, `tests/test_consent_gate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparator.py`:

```python
# ---------- v3: envelope two zones + guard ----------
def test_envelope_has_facts_table_and_synthesis_zones():
    resp = handle(mock_data.get_profile("1"))
    d = resp.data
    assert set(d["facts_table"]["rows"][0]["facts"]["fees"]) == {
        "text", "kind", "source_url", "fetched_at"}
    assert all(row["source_url"] is None
               for r in d["facts_table"]["rows"]
               for k, cell in r["facts"].items()
               for row in [cell] if cell["kind"] != "verified")
    assert d["synthesis"]["best_for_you"] is not None
    assert d["synthesis"]["weights"]
    assert "排名" in d["disclaimer"]


def test_priorities_via_slots():  # MIGRATED (replaces v2 version)
    resp = handle(mock_data.get_profile("1"), {"priorities": {"cost": 1.0}})
    assert resp.data["synthesis"]["weights"] == {"cost": 1.0}


def test_narrative_offline_deterministic():  # MIGRATED
    p = mock_data.get_profile("1")
    assert handle(p).data["synthesis"]["narrative"] == handle(p).data["synthesis"]["narrative"]


def test_ranking_narrative_falls_back(monkeypatch):
    from agents.comparator import agent as cagent
    monkeypatch.setattr(cagent.llm, "available", lambda: True)
    monkeypatch.setattr(cagent.llm, "explain", lambda *a, **k: "NUS 优于其他所有项目,排名第一")
    resp = handle(mock_data.get_profile("1"))
    assert "优于" not in resp.data["synthesis"]["narrative"]
    assert "排名" not in resp.data["synthesis"]["narrative"]
```

**Delete** the old v2 `test_disclaimer_and_provenance_in_handle`, and the old v2 `test_priorities_via_slots` / `test_narrative_offline_deterministic` (replaced above).

In `tests/test_consent_gate.py` replace `test_comparator_optout_drops_personalized_narrative` with:
```python
def test_comparator_optout_drops_synthesis_keeps_facts():
    from agents.comparator.agent import handle as chandle
    p = get_profile("1")
    p.consent_flags.personalization = False
    resp = chandle(p)
    assert resp.data["facts_table"]["rows"]        # objective table still present
    assert resp.data["synthesis"] is None          # personalised zone suppressed
    assert resp.data.get("personalized") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_comparator.py tests/test_consent_gate.py -k "envelope or priorities or narrative or optout or falls_back" -q`
Expected: FAIL — `data` has no `facts_table`/`synthesis`.

- [ ] **Step 3: Rewrite `agents/comparator/agent.py`**

Replace the file body below the module docstring with:

```python
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse
from common.profile import UserProfile

from .engine import compare, violates_ranking

_SYSTEM = (
    "You write a brief, balanced 'fit' summary comparing graduate programmes "
    "for one applicant. STRICT RULES: only use the facts provided; never rank "
    "programmes or say one is better than another; frame everything as fit to "
    "the applicant's stated goals; 2-3 sentences; no new facts."
)


def _narrative(comp, target_roles) -> str:
    role_text = "、".join(r.value for r in target_roles) if target_roles else "你的目标"
    fallback = (
        f"结合你的目标({role_text}),"
        + (f"{comp.best_for_you} 在相关方向的契合度较高。" if comp.best_for_you
           else "各项目各有侧重,建议按你的具体目标权衡。")
        + " 以下对比仅供参考。"
    )
    if not llm.available():
        return fallback
    facts = "\n".join(
        f"- {r.program}: "
        + "; ".join(f"{d}={c.text}" for d, c in r.facts.items() if c.kind == "verified")
        + f" (matches your goals on: {', '.join(r.synthesis.matched_roles) or 'none'})"
        for r in comp.rows
    )
    user = (
        f"Applicant goals: {role_text}\n"
        f"Best fit by overlap: {comp.best_for_you or 'n/a'}\n"
        f"Programmes:\n{facts}"
    )
    out = llm.explain(_SYSTEM, user, fallback)
    # Deterministic compliance guard: reject any cross-programme ranking claim.
    return fallback if violates_ranking(out) else out


def _facts_table(comp) -> dict:
    return {
        "rows": [
            {
                "program": r.program,
                "is_target": r.is_target,
                "facts": {
                    d: {"text": c.text, "kind": c.kind,
                        "source_url": c.source_url, "fetched_at": c.fetched_at}
                    for d, c in r.facts.items()
                },
            }
            for r in comp.rows
        ]
    }


def _synthesis(comp, narrative: str) -> dict:
    return {
        "rows": [
            {
                "program": r.program,
                "matched_roles": r.synthesis.matched_roles,
                "role_reasons": r.synthesis.role_reasons,
                "weighted_score": r.synthesis.weighted_score,
                "score_breakdown": r.synthesis.score_breakdown,
            }
            for r in comp.rows
        ],
        "best_for_you": comp.best_for_you,
        "narrative": narrative,
        "weights": comp.weights,
    }


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    priorities = slots.get("priorities")
    comp = compare(profile.target_roles, priorities)

    # consent gate (design doc 13 §5): opt-out -> objective facts only, the
    # entire personalised synthesis zone (scores + best_for_you + narrative) is
    # suppressed.
    personalized = profile.consent_flags.personalization
    if personalized:
        narrative = _narrative(comp, profile.target_roles)
        synthesis = _synthesis(comp, narrative)
        speakable = narrative
    else:
        synthesis = None
        speakable = ("以下是各项目的客观对比(已关闭个性化)。请按你的具体目标自行权衡;"
                     "对比基于公开整理数据,不构成排名。")
    if not profile.target_roles:
        speakable = ("你还没有设定目标岗位,以下是各项目的客观对比,"
                     "设定目标后我可以给出更贴合你的建议。")

    return AgentResponse(
        status="ok",
        answer_type="advisory",  # synthesis, not official policy
        speakable=speakable,
        data={
            "dimensions": comp.dimensions,
            "facts_table": _facts_table(comp),
            "synthesis": synthesis,                 # None when opted out
            "disclaimer": comp.disclaimer,          # always present (compliance)
            "personalized": personalized,
        },
        sources=["programs_dataset"],
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_comparator.py tests/test_consent_gate.py -q`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: full suite green except the student-template render is still old (Task 7). If `tests/test_student.py` asserts on comparison output shape, it may fail here — fix in Task 7. Confirm `python -m eval.runner` still prints `12/12`. Suggested commit msg: `feat(#6): two-zone envelope + narrative guard + consent gate`.

---

## Task 7: Student results template — two-zone render

**Files:**
- Modify: `student/templates/results.html:180-205` (the `#6 Comparison` section)
- Test: `tests/test_student.py` (adjust only if it asserts old comparison keys)

- [ ] **Step 1: Check the existing student test**

Run: `python -m pytest tests/test_student.py -q`
If green, the template change below is render-only; re-run after editing. If a test asserts `m.data["rows"]` / `m.data["narrative"]` / `m.data["best_for_you"]`, update those assertions to the new paths: `m.data["facts_table"]["rows"]`, `m.data["synthesis"]["narrative"]`, `m.data["synthesis"]["best_for_you"]` (synthesis may be `None`).

- [ ] **Step 2: Replace the `#6 Comparison` block** (`{% if r.comparison is defined %}` … `</section>`) with:

```html
{% if r.comparison is defined %}
<section id="compare" class="panel reveal">
  <div class="panel__head"><h2 class="panel__title"><span class="panel__icon">⚖️</span> 项目对比</h2></div>
  {% set m = r.comparison %}
  {% if m.status == "ok" %}
    {# ----- Verified facts table ----- #}
    <div class="table-scroll" style="margin-top:12px">
      <table>
        <tr><th>项目</th>{% for d in m.data["dimensions"] %}<th>{{ d }}</th>{% endfor %}<th>来源</th></tr>
        {% for row in m.data["facts_table"]["rows"] %}
        <tr class="{{ 'is-target-row' if row.is_target }}">
          <td class="{{ 'is-target' if row.is_target }}">{{ row.program }}{% if row.is_target %} <span class="star">★</span>{% endif %}</td>
          {% for d in m.data["dimensions"] %}
            {% set cell = row["facts"].get(d) %}
            <td>
              {% if cell %}{{ cell.text }}
                {% if cell.kind == "unknown" %}<br><span class="why">未公开</span>
                {% elif cell.kind == "synthesis" %}<br><span class="why">AI 综合</span>{% endif %}
              {% endif %}
            </td>
          {% endfor %}
          <td>
            {% set src = (row["facts"].get("fees") or {}).get("source_url") %}
            {% for d in m.data["dimensions"] %}{% set c = row["facts"].get(d) %}{% if c and c.source_url %}{% set src = c.source_url %}{% endif %}{% endfor %}
            {% if src %}<a href="{{ src }}" target="_blank" rel="noopener">官方页 ↗</a>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
    <div class="note" style="margin-top:8px"><span class="why">事实表来自各校官方公开页(verified);标「未公开」为官方未披露,标「AI 综合」为系统归纳的非官方解读。</span></div>

    {# ----- AI synthesis zone (suppressed when personalization off) ----- #}
    {% if m.data["synthesis"] %}
    <div class="note note--info" style="margin-top:16px">
      <strong>AI 综合分析(非官方事实)</strong>
      <p style="margin:8px 0 0">{{ m.data["synthesis"]["narrative"] }}</p>
      {% if m.data["synthesis"]["best_for_you"] %}
      <p style="margin:8px 0 0">按你的偏好权重 {{ m.data["synthesis"]["weights"] }},<strong>{{ m.data["synthesis"]["best_for_you"] }}</strong> 在当前规则下更契合你的目标;这不是学校排名。</p>
      {% endif %}
      <ul style="margin:8px 0 0">
        {% for sr in m.data["synthesis"]["rows"] %}
        <li><span class="why">{{ sr.program }}: fit={{ sr.weighted_score }}</span></li>
        {% endfor %}
      </ul>
    </div>
    {% else %}
    <div class="note" style="margin-top:16px"><span class="why">已关闭个性化:仅显示客观事实对比。</span></div>
    {% endif %}

    <div class="note" style="margin-top:12px">{{ m.data["disclaimer"] }}</div>
  {% endif %}
</section>
{% endif %}
```

- [ ] **Step 3: Run to verify pass**

Run: `python -m pytest tests/test_student.py -q`
Expected: PASS.

- [ ] **Step 4: Smoke-render check**

Run:
```bash
python -c "from student.webapp import app; c=app.test_client(); import json; print('ok')"
```
Expected: prints `ok` (imports the Flask app without template syntax errors). If the app needs a route to render, instead trust `tests/test_student.py`.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: full suite PASS. Suggested commit msg: `feat(#6): student template renders fact/synthesis zones`.

---

## Task 8: Docs + CHANGELOG + overview

**Files:**
- Modify: `docs/02-interface-contracts.md` (§4 #6 data shape)
- Modify: `docs/09-comparator-v2-design.md` (supersession note)
- Modify: `CHANGELOG.md`, `docs/00-project-overview.md`

- [ ] **Step 1: Update contract §4 #6** in `docs/02-interface-contracts.md` — replace the `#6 compare_programs → data` jsonc block with the v3 shape:

````markdown
### #6 `compare_programs` → data (v3: fact/synthesis split)
```jsonc
{
  "dimensions": ["curriculum_focus","duration","format","fees","intake","scholarship","gmat_gre",
                 "typical_profile","industry_orientation","technical_depth","career_pathways"],
  "facts_table": {                       // 仅事实(verified/unknown)
    "rows": [
      { "program": "NUS ...", "is_target": true,
        "facts": { "fees": {"text":"S$74,120 ...","kind":"verified","source_url":"...","fetched_at":"2026-06-05"},
                   "technical_depth": {"text":"...","kind":"synthesis","source_url":null,"fetched_at":null} } }
    ]
  },
  "synthesis": {                         // 派生/AI;关闭个性化时为 null
    "rows": [ { "program":"NUS ...", "matched_roles":["fintech_pm"], "role_reasons":{...},
                "weighted_score":0.0, "score_breakdown":{"role_fit":0,"cost":0.5,"duration":1} } ],
    "best_for_you": "NUS ...",
    "narrative": "...",                  // 过 violates_ranking 护栏
    "weights": {"role_fit":1.0}
  },
  "disclaimer": "对比基于公开整理数据, 不构成排名。",  // 恒在
  "personalized": true
}
```
> 🔒 合规:`facts_table` 仅事实(每格带 `kind` 与来源);`synthesis` 为非官方综合,opt-out 时整块为 `null`;`narrative` 经确定性防排名护栏。
````

- [ ] **Step 2: Add a supersession note** at the top of `docs/09-comparator-v2-design.md`:

```markdown
> **v3 起(2026-06-08)**:数据/输出升级为三态 cell(verified/unknown/synthesis)+ facts/synthesis 分区 + 确定性防排名护栏,展示维度扩到 11(含 PDF 4 维)。见 [v3 spec](superpowers/specs/2026-06-08-comparator-fact-synthesis-design.md) 与 [v3 plan](superpowers/plans/2026-06-08-comparator-fact-synthesis.md)。本文档描述的 v2 加权评分(role_fit/cost/duration)在 v3 中**不变**。
```

- [ ] **Step 3: Append a CHANGELOG entry** under `## [Unreleased]` → `### 2026-06-08` in `CHANGELOG.md`:

```markdown
- **D · #6 Comparator v3(已落地)**:三态 cell(`verified`/`unknown`/`synthesis`)+ loader 规范化;展示维度扩到 11(含 PDF 的 typical_profile/industry_orientation/technical_depth/career_pathways);评分仍只读 verified 的 3 信号;engine 输出 facts/synthesis 两分;`violates_ranking` 确定性防排名护栏;envelope `data.facts_table` + `data.synthesis` 两区(opt-out 时 synthesis=null);学生页两区渲染;schema 接受三态 cell。契约 §4#6 更新。
```

- [ ] **Step 4: Update `docs/00-project-overview.md`** — in the §4 agent table, change the #6 row's "关键特性" cell from `**正在做 v3...**` to:
```markdown
rows 只来自人工审核数据集;disclaimer 恒在;**v3 已落地:三态 cell + facts/synthesis 分区 + 确定性防排名护栏(展示 11 维)**
```
And in §6 table, change the **D** row status from `⬜ **进行中**` to `✅ 已落地`.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: full suite PASS (docs don't affect tests; this confirms nothing regressed). Suggested commit msg: `docs(#6): update contract/overview/changelog for comparator v3`.

---

## Task 9: Final verification

- [ ] **Step 1: Full suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS (prior baseline was 205 passed + 1 skipped; v3 adds ~16 tests and migrates ~5 — expect ~221 passed + 1 skipped, exact count may differ).

- [ ] **Step 2: Eval regression**

Run: `python -m eval.runner`
Expected: scorecard `12/12` (unchanged — comparator not in eval cases).

- [ ] **Step 3: CLI smoke**

Run: `python run.py compare --profile 1`
Expected: prints a comparison without error.

- [ ] **Step 4: JSON validity**

Run: `python -c "import json; json.load(open('data/programs_dataset.json',encoding='utf-8')); print('json ok')"`
Expected: `json ok`.
