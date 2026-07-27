# 个性化 taxonomy + 公平性(方向 C)— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把分散的手工 skill rubric 升级为统一的 curated taxonomy + 可插拔 embedding 语义匹配器(背景→技能、技能/角色→模块),加 consent gate(opt-out → 通用推荐)与公平性约束(排除 country),阈值用 eval 网格校准。

**Architecture:** `SkillMatcher` 接口(`EmbeddingSkillMatcher` 主 + `RuleSkillMatcher` 降级,工厂按 embedding 可用性选),消费 `data/skill_taxonomy.json`;复用 A 的 `common/embeddings.py` + 指纹向量缓存 + `eval` 校准框架。navigator 用匹配①②,navigator/comparator 入口加 consent gate,公平性靠"background_text 排除 country" + 不变量测试。

**Tech Stack:** Python 3.11 / pydantic / openai(Ollama OpenAI 兼容)/ pytest。embedding = Ollama `nomic-embed-text`(A 已接)。

> **环境:** 非 git 仓库。所有 "Checkpoint" 用 `python -m pytest tests/ -q` 全绿代替 commit。设计见 [`docs/13-personalization-fairness-design.md`](../../13-personalization-fairness-design.md)。说明:本计划 taxonomy 省略 spec 的可选 `rule_hints`(MVP 的 `RuleSkillMatcher` 直接复用现有确定性 `derive_user_skills` + 固定 `recommended_modules`,行为不变更可靠);embedding 路径用 taxonomy 的 `description`。

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `data/skill_taxonomy.json` | curated 技能子集(9 核心 skill,统一现有定义) | Create |
| `common/skill_taxonomy.py` | `SkillDef` + `load_taxonomy()` | Create |
| `common/skill_matcher.py` | `SkillMatcher` 接口 + `RuleSkillMatcher` + `EmbeddingSkillMatcher` + `get_skill_matcher()` + `background_text()` | Create |
| `eval/cases/skill_match.json` | 背景→技能 标注集 | Create |
| `eval/skill_calibrate.py` | 阈值网格校准 | Create |
| `data/match_thresholds.json` | 校准产出(按后端分节) | Create |
| `agents/navigator/engine.py` | `guide_for_role` 改用 matcher;入口 consent gate | Modify |
| `agents/navigator/agent.py` | consent gate(personalization False → 通用) | Modify |
| `agents/comparator/agent.py` | consent gate(personalization False → 去个性化叙述) | Modify |
| `.gitignore` | 忽略 `data/_skill_vectors.json` | Modify |
| `tests/test_skill_taxonomy.py` `test_skill_matcher.py` `test_skill_calibrate.py` `test_consent_gate.py` `test_fairness.py` | 测试 | Create |

---

# 阶段 1 — taxonomy + 规则降级(离线)

## Task 1: skill taxonomy 数据 + 加载

**Files:** Create `data/skill_taxonomy.json`, `common/skill_taxonomy.py`; Test `tests/test_skill_taxonomy.py`.

- [ ] **Step 1: 写 `data/skill_taxonomy.json`**(9 核心 skill,id 对齐现有 `role_module_map.json` 的 skill tag)

```json
{
  "_comment": "Curated DFT skill taxonomy. ids match role_module_map.json skill tags. framework codes are curated references to ESCO/O*NET (not API calls).",
  "skills": [
    {"id": "programming", "label": "编程能力", "aliases": ["software development", "coding", "编程"], "framework": {"esco": "S5.6", "onet": "2.B.3.e"}, "description": "Writing and understanding software; programming languages, data structures, engineering practices."},
    {"id": "data_analytics", "label": "数据分析", "aliases": ["data analysis", "analytics", "数据科学"], "framework": {"esco": "S1.7", "onet": "2.A.1.e"}, "description": "Analysing data, statistics, visualisation and drawing insights from datasets."},
    {"id": "finance", "label": "金融知识", "aliases": ["finance", "financial markets", "金融"], "framework": {"esco": "S2.1", "onet": "2.C.7.a"}, "description": "Financial markets, instruments, banking, corporate finance fundamentals."},
    {"id": "risk_modeling", "label": "风险建模", "aliases": ["quantitative risk", "risk management", "风险量化"], "framework": {"esco": "S1.2.6", "onet": "2.B.2.i"}, "description": "Quantitative methods for measuring and managing financial risk; modelling and stress testing."},
    {"id": "product", "label": "产品/业务理解", "aliases": ["product management", "business", "产品管理"], "framework": {"esco": "S4.8", "onet": "2.B.1.e"}, "description": "Product strategy, business understanding, translating user needs into product decisions."},
    {"id": "regulation", "label": "合规/监管", "aliases": ["compliance", "regulatory", "监管", "合规"], "framework": {"esco": "S2.3", "onet": "2.C.1.e"}, "description": "Financial regulation, compliance, anti-money-laundering and supervisory requirements."},
    {"id": "payments_systems", "label": "支付/区块链/交易系统", "aliases": ["payments", "blockchain", "digital assets", "支付", "区块链"], "framework": {"esco": "S5.3", "onet": "2.B.3.j"}, "description": "Payment systems, blockchain, distributed ledgers, digital assets and transaction infrastructure."},
    {"id": "security", "label": "安全与韧性", "aliases": ["cyber security", "resilience", "安全"], "framework": {"esco": "S5.4", "onet": "2.B.3.g"}, "description": "Information security, cyber resilience, technology risk and system robustness."},
    {"id": "ai_ml", "label": "AI / Machine Learning", "aliases": ["machine learning", "artificial intelligence", "机器学习"], "framework": {"esco": "S1.7.2", "onet": "2.B.3.m"}, "description": "Machine learning and AI methods applied to finance and analytics."}
  ]
}
```

- [ ] **Step 2: 写失败测试 `tests/test_skill_taxonomy.py`**

```python
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
```

- [ ] **Step 3: 运行确认失败** — `python -m pytest tests/test_skill_taxonomy.py -q` → `ModuleNotFoundError: No module named 'common.skill_taxonomy'`

- [ ] **Step 4: 写 `common/skill_taxonomy.py`**

```python
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
```

- [ ] **Step 5: 运行确认通过** — `python -m pytest tests/test_skill_taxonomy.py -q` (3 passed)
- [ ] **Step 6: Checkpoint** — `python -m pytest tests/ -q` (all pass)

---

## Task 2: SkillMatcher 接口 + RuleSkillMatcher + 工厂

**Files:** Create `common/skill_matcher.py`; Test `tests/test_skill_matcher.py`.

依赖现有 `agents/navigator/engine.py`:`derive_user_skills(profile) -> set[str]`、`guide_for_role` 用的 `role_module_map.json`(`roles[role]["recommended_modules"]` = list of `{code, name}`、`required_skills`、`skill_labels`)。

- [ ] **Step 1: 写失败测试 `tests/test_skill_matcher.py`**

```python
"""Tests for common.skill_matcher (rule backend + factory)."""
from __future__ import annotations

from common.mock_data import get_profile
from common.skill_matcher import RuleSkillMatcher, SkillHit, get_skill_matcher, background_text


def test_background_text_excludes_country():
    p = get_profile("1")  # country=IN
    txt = background_text(p)
    assert "IN" not in txt and "India" not in txt
    assert "banking" in txt  # work_domain IS included (capability signal)


def test_rule_infer_user_skills_matches_legacy():
    # RuleSkillMatcher reproduces derive_user_skills exactly.
    from agents.navigator.engine import derive_user_skills
    p = get_profile("5")
    hits = RuleSkillMatcher().infer_user_skills(p)
    assert {h.id for h in hits} == derive_user_skills(p)
    assert all(isinstance(h, SkillHit) for h in hits)


def test_rule_recommend_modules_for_role():
    p = get_profile("1")
    hits = RuleSkillMatcher().recommend_modules("fintech_pm", {"product", "finance"})
    codes = {h.code for h in hits}
    assert "BMS5312" in codes  # from role_module_map fintech_pm


def test_factory_returns_rule_when_embedding_unavailable(monkeypatch):
    from common import skill_matcher
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: False)
    assert isinstance(get_skill_matcher(), RuleSkillMatcher)
```

- [ ] **Step 2: 运行确认失败** — `ModuleNotFoundError: No module named 'common.skill_matcher'`

- [ ] **Step 3: 写 `common/skill_matcher.py`**(先接口 + Rule + 工厂;Embedding 在 Task 4 追加)

```python
"""Pluggable skill/module matcher (design doc 13 §4).

SkillMatcher is the seam: an embedding backend (semantic) and a rule backend
(the existing deterministic logic, offline fallback). Both return explainable
hits (id/label/score/source).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from common.profile import UserProfile

_RM_PATH = Path(__file__).resolve().parents[1] / "data" / "role_module_map.json"


@dataclass(frozen=True)
class SkillHit:
    id: str
    label: str
    score: float
    source: str  # "rule" | "embedding"


@dataclass(frozen=True)
class ModuleHit:
    code: str
    name: str
    score: float
    source: str


class SkillMatcher(Protocol):
    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]: ...
    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]: ...


def background_text(profile: UserProfile) -> str:
    """Capability-only text for embedding. EXCLUDES country (fairness, doc 13 §6)."""
    parts: list[str] = []
    ab = profile.academic_background
    if ab:
        parts.append(f"degree {ab.degree_level.value} in {ab.field_of_study.value}")
    if profile.work_domain:
        parts.append(f"work domain {profile.work_domain.value}")
    if profile.work_years is not None:
        parts.append(f"{profile.work_years} years experience")
    if profile.technical_proficiency:
        parts.append(f"technical {profile.technical_proficiency.value}")
    if profile.finance_knowledge:
        parts.append(f"finance knowledge {profile.finance_knowledge.value}")
    if profile.completed_modules:
        parts.append("completed " + ", ".join(profile.completed_modules))
    return "; ".join(parts)


def _load_rm() -> dict:
    return json.loads(_RM_PATH.read_text(encoding="utf-8"))


class RuleSkillMatcher:
    """Deterministic offline backend: reuses the existing rule logic."""

    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]:
        from agents.navigator.engine import derive_user_skills
        from common.skill_taxonomy import load_taxonomy

        labels = {s.id: s.label for s in load_taxonomy()}
        return [SkillHit(id=s, label=labels.get(s, s), score=1.0, source="rule")
                for s in sorted(derive_user_skills(profile))]

    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]:
        role_def = _load_rm()["roles"][role]
        return [ModuleHit(code=m["code"], name=m["name"], score=1.0, source="rule")
                for m in role_def["recommended_modules"]]


def get_skill_matcher() -> SkillMatcher:
    """Embedding backend when available, else the offline rule backend."""
    try:
        from common.embeddings import embedding_available

        if embedding_available():
            return EmbeddingSkillMatcher()
    except Exception:
        pass
    return RuleSkillMatcher()
```

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_skill_matcher.py -q` (4 passed)。注:`get_skill_matcher` 引用未定义的 `EmbeddingSkillMatcher` 仅在 embedding 可用分支,测试 monkeypatch 为不可用 → 走 Rule;离线 conftest 同理。
- [ ] **Step 5: Checkpoint** — `python -m pytest tests/ -q`

---

# 阶段 2 — embedding 匹配器

## Task 3: EmbeddingSkillMatcher + 向量缓存

**Files:** Modify `common/skill_matcher.py`; Modify `.gitignore`; Test `tests/test_skill_matcher.py`.

- [ ] **Step 1: 追加失败测试到 `tests/test_skill_matcher.py`**

```python
def test_embedding_infer_ranks_by_cosine(monkeypatch, tmp_path):
    from common import skill_matcher as M

    def fake_embed(texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "risk" in tl or "quantitative" in tl:
                out.append([1.0, 0.0])
            elif "payment" in tl or "blockchain" in tl:
                out.append([0.0, 1.0])
            else:
                out.append([0.4, 0.4])
        return out

    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "stub")

    em = M.EmbeddingSkillMatcher(skill_threshold=0.8)
    # a risk-heavy background should surface risk_modeling
    from common.mock_data import get_profile
    p = get_profile("3")  # advanced tech
    # force a risk-y background text
    monkeypatch.setattr(M, "background_text", lambda _p: "quantitative risk modelling")
    hits = em.infer_user_skills(p)
    assert hits and hits[0].id == "risk_modeling"
    assert hits[0].source == "embedding"


def test_embedding_cache_rebuilds_on_model_change(monkeypatch, tmp_path):
    from common import skill_matcher as M

    calls = {"n": 0}

    def fake_embed(texts):
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-A")
    M.EmbeddingSkillMatcher()
    n_a = calls["n"]
    M.EmbeddingSkillMatcher()  # same model -> cache reused
    assert calls["n"] == n_a
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-B")
    M.EmbeddingSkillMatcher()  # changed -> rebuild
    assert calls["n"] > n_a
```

- [ ] **Step 2: 运行确认失败** — `AttributeError: ... 'EmbeddingSkillMatcher'`

- [ ] **Step 3: 追加到 `common/skill_matcher.py`**(顶部加 `import math` 与 `from common import config, embeddings`;然后追加)

```python
_VEC_DIR = Path(__file__).resolve().parents[1] / "data"


def _skill_cache_path() -> Path:
    return _VEC_DIR / "_skill_vectors.json"


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


class EmbeddingSkillMatcher:
    """Semantic backend over the taxonomy + module_catalog, fingerprinted cache."""

    def __init__(self, skill_threshold: float = 0.5, module_threshold: float = 0.5) -> None:
        from common.skill_taxonomy import load_taxonomy

        self.skill_threshold = skill_threshold
        self.module_threshold = module_threshold
        self._skills = load_taxonomy()
        self._model = config.get_embedding_model()
        self._skill_vecs = self._load_or_build_cache()

    def _load_or_build_cache(self) -> dict[str, list[float]]:
        path = _skill_cache_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("model") == self._model:
                    return data.get("vectors", {})
            except (json.JSONDecodeError, OSError):
                pass
        texts = [f"{s.label}. {s.description}. {', '.join(s.aliases)}" for s in self._skills]
        vecs = embeddings.embed_texts(texts)
        vectors = {s.id: v for s, v in zip(self._skills, vecs)}
        try:
            path.write_text(json.dumps({"model": self._model, "vectors": vectors}),
                            encoding="utf-8")
        except OSError:
            pass
        return vectors

    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]:
        qv = embeddings.embed_texts([background_text(profile)])[0]
        labels = {s.id: s.label for s in self._skills}
        scored = [(sid, _cosine(qv, vec)) for sid, vec in self._skill_vecs.items()]
        scored = [(sid, sc) for sid, sc in scored if sc >= self.skill_threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [SkillHit(id=sid, label=labels.get(sid, sid), score=round(sc, 4),
                         source="embedding") for sid, sc in scored]

    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]:
        # Reuse the rule recommendation set as the candidate pool, re-ranked by
        # semantic fit to the user's skills (keeps curated modules, adds ordering).
        from common.skill_taxonomy import load_taxonomy

        defs = {s.id: s for s in load_taxonomy()}
        skill_text = ". ".join(defs[s].description for s in user_skills if s in defs) or role
        qv = embeddings.embed_texts([skill_text])[0]
        pool = RuleSkillMatcher().recommend_modules(role, user_skills)
        mod_texts = [f"{m.name}" for m in pool]
        mvecs = embeddings.embed_texts(mod_texts) if mod_texts else []
        ranked = sorted(
            ((m, _cosine(qv, mv)) for m, mv in zip(pool, mvecs)),
            key=lambda x: x[1], reverse=True,
        )
        return [ModuleHit(code=m.code, name=m.name, score=round(sc, 4),
                          source="embedding") for m, sc in ranked]
```

- [ ] **Step 4: `.gitignore` 末尾追加** — `data/_skill_vectors.json`
- [ ] **Step 5: 运行确认通过** — `python -m pytest tests/test_skill_matcher.py -q`(全部，含 2 新）。确认无真实 `data/_skill_vectors.json`（桩重定向 tmp_path）。
- [ ] **Step 6: Checkpoint** — `python -m pytest tests/ -q`

---

# 阶段 3 — 阈值校准

## Task 4: 标注集 + skill_calibrate

**Files:** Create `eval/cases/skill_match.json`, `eval/skill_calibrate.py`; Test `tests/test_skill_calibrate.py`.

- [ ] **Step 1: 写 `eval/cases/skill_match.json`**(profile → 期望 user-skill id，金标按背景独立推断，与 mock_data 一致）

```json
[
  {"profile_ref": "1", "gold_skills": ["programming", "data_analytics", "finance"]},
  {"profile_ref": "3", "gold_skills": ["programming", "data_analytics", "risk_modeling", "ai_ml", "security"]},
  {"profile_ref": "5", "gold_skills": ["programming", "data_analytics", "risk_modeling", "ai_ml", "security", "finance", "payments_systems", "product"]},
  {"profile_ref": "2", "gold_skills": ["finance", "regulation"]}
]
```

- [ ] **Step 2: 写失败测试 `tests/test_skill_calibrate.py`**

```python
"""Tests for eval.skill_calibrate — threshold sweep for skill matching."""
from __future__ import annotations

from eval.skill_calibrate import load_cases, evaluate_threshold, grid_search


def test_cases_load():
    cs = load_cases()
    assert len(cs) >= 4
    assert all("gold_skills" in c for c in cs)


def test_evaluate_threshold_returns_f1():
    cs = load_cases()
    from common.skill_matcher import RuleSkillMatcher
    r = evaluate_threshold(cs, 0.5, matcher=RuleSkillMatcher())
    assert 0.0 <= r["f1"] <= 1.0
    assert r["threshold"] == 0.5


def test_grid_search_picks_best_f1():
    cs = load_cases()
    from common.skill_matcher import RuleSkillMatcher
    best, table = grid_search(cs, matcher=RuleSkillMatcher())
    assert best in table
    assert best["f1"] == max(r["f1"] for r in table)
```

- [ ] **Step 3: 运行确认失败** — `ModuleNotFoundError: No module named 'eval.skill_calibrate'`

- [ ] **Step 4: 写 `eval/skill_calibrate.py`**

```python
"""Skill-match threshold calibration (design doc 13 §4.4).

Sweep the skill_threshold against a labelled set (profile -> gold skill ids),
score by mean F1 (eval.metrics.set_prf), pick the most robust best cell. Uses the
active matcher; re-run after a model swap. RuleSkillMatcher ignores the threshold
(deterministic) — calibration is meaningful for the embedding backend.

    python -m eval.skill_calibrate [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common.skill_matcher import get_skill_matcher
from eval.metrics import set_prf

_CASES = Path(__file__).resolve().parent / "cases" / "skill_match.json"
_THRESHOLDS = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]


def load_cases() -> list[dict]:
    return json.loads(_CASES.read_text(encoding="utf-8"))


def _matcher_at(matcher, threshold):
    # EmbeddingSkillMatcher carries a threshold; rebuild at this threshold.
    from common.skill_matcher import EmbeddingSkillMatcher
    if isinstance(matcher, EmbeddingSkillMatcher):
        return EmbeddingSkillMatcher(skill_threshold=threshold)
    return matcher  # rule backend: threshold-independent


def evaluate_threshold(cases: list[dict], threshold: float, matcher=None) -> dict:
    from common.mock_data import get_profile
    matcher = _matcher_at(matcher or get_skill_matcher(), threshold)
    f1s = []
    for c in cases:
        pred = {h.id for h in matcher.infer_user_skills(get_profile(c["profile_ref"]))}
        f1s.append(set_prf(pred, c["gold_skills"])["f1"])
    mean = sum(f1s) / len(f1s) if f1s else 0.0
    return {"threshold": threshold, "f1": round(mean, 4), "n": len(cases)}


def grid_search(cases: list[dict], matcher=None) -> tuple[dict, list[dict]]:
    base = matcher or get_skill_matcher()
    table = [evaluate_threshold(cases, t, matcher=base) for t in _THRESHOLDS]
    best_f1 = max(r["f1"] for r in table)
    top = [r for r in table if r["f1"] == best_f1]
    best = top[len(top) // 2]  # median threshold among ties (robust)
    return best, table


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    best, table = grid_search(load_cases())
    if "--json" in argv:
        print(json.dumps({"best": best, "grid": table}, ensure_ascii=False, indent=2))
    else:
        for r in table:
            print(f"  thr={r['threshold']:.2f}  f1={r['f1']:.3f}")
        print(f"\nBEST: skill_threshold={best['threshold']:.2f} f1={best['f1']:.3f} (n={best['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行确认通过** — `python -m pytest tests/test_skill_calibrate.py -q` (3 passed)
- [ ] **Step 6: Checkpoint** — `python -m pytest tests/ -q`

> 校准产出写入 `data/match_thresholds.json` 在 Task 5 与 consent/接入一起落地(需 embedding 实跑，运维步骤）。

---

# 阶段 4 — consent gate + 公平性 + 接入

## Task 5: match_thresholds.json + matcher 读取

**Files:** Create `data/match_thresholds.json`; Modify `common/skill_matcher.py`; Test `tests/test_skill_matcher.py`.

- [ ] **Step 1: 写 `data/match_thresholds.json`**(按后端分节，初值为经验值，embedding 实跑校准后覆盖）

```json
{
  "embedding": {"skill_threshold": 0.50, "module_threshold": 0.50},
  "rule": {"skill_threshold": 1.0, "module_threshold": 1.0},
  "_note": "per-backend match thresholds (eval.skill_calibrate). rule backend ignores thresholds. Re-run after embedding model change."
}
```

- [ ] **Step 2: 追加失败测试**

```python
def test_factory_applies_embedding_thresholds(monkeypatch, tmp_path):
    from common import skill_matcher as M
    import json
    f = tmp_path / "mt.json"
    f.write_text(json.dumps({"embedding": {"skill_threshold": 0.61, "module_threshold": 0.62}}),
                 encoding="utf-8")
    monkeypatch.setattr(M, "_THRESHOLDS_PATH", f)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)
    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "stub")
    m = M.get_skill_matcher()
    assert m.skill_threshold == 0.61
```

- [ ] **Step 3: 运行确认失败** — `AttributeError: ... '_THRESHOLDS_PATH'`

- [ ] **Step 4: 改 `common/skill_matcher.py`**：顶部加 `_THRESHOLDS_PATH` 与读取函数，`get_skill_matcher` 用它构造 Embedding：

```python
_THRESHOLDS_PATH = _VEC_DIR / "match_thresholds.json"


def _match_thresholds(backend: str) -> dict:
    defaults = {"skill_threshold": 0.5, "module_threshold": 0.5}
    try:
        data = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        section = data.get(backend, {})
        return {k: float(section.get(k, defaults[k])) for k in defaults}
    except (OSError, ValueError):
        return defaults
```

并把 `get_skill_matcher` 的 embedding 分支改为：

```python
        if embedding_available():
            t = _match_thresholds("embedding")
            return EmbeddingSkillMatcher(skill_threshold=t["skill_threshold"],
                                         module_threshold=t["module_threshold"])
```

(注：`_THRESHOLDS_PATH`/`_match_thresholds` 必须定义在 `get_skill_matcher` 之前，或在函数内引用模块级名——放文件靠上、`EmbeddingSkillMatcher` 之后即可。)

- [ ] **Step 5: 运行确认通过 + Checkpoint** — `python -m pytest tests/test_skill_matcher.py tests/ -q`

---

## Task 6: consent gate + 公平性接入 navigator

**Files:** Modify `agents/navigator/engine.py`, `agents/navigator/agent.py`; Test `tests/test_consent_gate.py`, `tests/test_fairness.py`.

navigator 现状：`guide_for_role(profile, role)` 用 `derive_user_skills` + 固定 modules 算 `skill_gaps`。改为经 `get_skill_matcher()`；agent 入口加 consent gate。

- [ ] **Step 1: 写失败测试 `tests/test_consent_gate.py`**

```python
"""personalization opt-out -> generic recommendation (no skill-gap)."""
from __future__ import annotations

from common.mock_data import get_profile
from agents.navigator.agent import handle


def test_optout_returns_generic_no_skill_gap():
    p = get_profile("1")
    p.consent_flags.personalization = False
    resp = handle(p, {"target_role": "fintech_pm"})
    assert resp.status == "ok"
    assert resp.data["recommended_modules"]          # still gives modules
    assert resp.data.get("skill_gaps") == []         # but NO personalised gap
    assert resp.data.get("personalized") is False


def test_optin_keeps_skill_gap():
    p = get_profile("1")
    p.consent_flags.personalization = True
    resp = handle(p, {"target_role": "fintech_pm"})
    assert resp.data.get("personalized") is True
```

- [ ] **Step 2: 写失败测试 `tests/test_fairness.py`**

```python
"""Fairness: country must not affect skill inference or recommendations."""
from __future__ import annotations

from common.mock_data import get_profile
from common.skill_matcher import RuleSkillMatcher, background_text


def test_background_text_country_invariant():
    a = get_profile("1")            # country IN
    b = get_profile("1"); b.country = "SG"
    assert background_text(a) == background_text(b)


def test_skill_inference_country_invariant():
    a = get_profile("1")
    b = get_profile("1"); b.country = "US"
    m = RuleSkillMatcher()
    assert {h.id for h in m.infer_user_skills(a)} == {h.id for h in m.infer_user_skills(b)}
```

- [ ] **Step 3: 运行确认失败** — consent/personalized 字段与行为尚不存在

- [ ] **Step 4: 改 `agents/navigator/agent.py` `handle`**：入口加 consent gate，data 加 `personalized` 标记，opt-out 时 `skill_gaps=[]`。在 `g = guide_for_role(...)` 后插入：

```python
    personalized = profile.consent_flags.personalization
    skill_gaps = g.skill_gap_labels if personalized else []
    gap_text = "、".join(skill_gaps) if skill_gaps else "无明显技能缺口"
```

把后续 `fallback` / `data` 中的 `g.skill_gap_labels` 改用 `skill_gaps`，并在 `data` 加 `"personalized": personalized`。（`recommended_modules` 仍返回，保证通用推荐可用。）

- [ ] **Step 5: 运行确认通过** — `python -m pytest tests/test_consent_gate.py tests/test_fairness.py -q`
- [ ] **Step 6: Checkpoint** — `python -m pytest tests/ -q`（navigator 既有测试不回归）

---

## Task 7: comparator consent gate + 文档收尾

**Files:** Modify `agents/comparator/agent.py`; Modify `docs/11`, `README.md`; Test `tests/test_consent_gate.py`.

- [ ] **Step 1: 追加失败测试到 `tests/test_consent_gate.py`**

```python
def test_comparator_optout_drops_personalized_narrative():
    from agents.comparator.agent import handle as chandle
    p = get_profile("1")
    p.consent_flags.personalization = False
    resp = chandle(p)
    # objective table still present; best_for_you personalisation suppressed
    assert resp.data["rows"]
    assert resp.data.get("personalized") is False
    assert resp.data.get("best_for_you") is None
```

- [ ] **Step 2: 运行确认失败**

- [ ] **Step 3: 改 `agents/comparator/agent.py` `handle`**：consent gate 抑制个性化结论。在 `comp = compare(...)` 后：

```python
    personalized = profile.consent_flags.personalization
    best_for_you = comp.best_for_you if personalized else None
```

`narrative` 在 `not personalized` 时用中性版（不提 best fit）；`data` 里 `best_for_you` 用 `best_for_you`，并加 `"personalized": personalized`。

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_consent_gate.py -q`

- [ ] **Step 5: 文档**：`docs/11` §4(C 节)末尾加 `**状态:已落地(W5)**`；`README.md` 加一节：

```markdown
## 个性化 taxonomy + 公平性(研究方向 C)
- 统一 `data/skill_taxonomy.json`(ESCO/O*NET 编码引用);`common/skill_matcher.py` 可插拔:embedding 语义匹配(背景→技能 / 技能→模块)+ 规则降级。
- consent:`personalization=False` → 通用推荐(无 skill-gap)。公平性:背景文本排除 country,不变量测试保证国籍不影响推荐。
- 阈值校准:`python -m eval.skill_calibrate`(写 `data/match_thresholds.json`)。详见 [设计](docs/13-personalization-fairness-design.md)。
```

- [ ] **Step 6: Checkpoint(最终)** — `python -m pytest tests/ -q`(全绿)

---

## 自审记录(spec coverage)

- §3 taxonomy 数据 + 加载 → Task 1 ✅
- §4.1 SkillMatcher 接口 + 工厂 → Task 2 ✅
- §4.3 RuleSkillMatcher → Task 2 ✅
- §4.2 EmbeddingSkillMatcher + 指纹缓存 → Task 3 ✅
- §4.4 校准(标注集 + skill_calibrate + match_thresholds 按后端) → Task 4 + Task 5 ✅
- §5 consent gate(navigator + comparator) → Task 6 + Task 7 ✅
- §6 公平性(background_text 排除 country + 不变量测试) → Task 2(background_text) + Task 6(test_fairness) ✅
- §7 测试(桩确定性 / 离线降级) → 各 Task ✅
- §8 四阶段 → Task 1-2 / 3 / 4-5 / 6-7 ✅
- 边界:#4 Checklist 国籍规则不受约束 → 不改 checklist(计划未触碰) ✅
