# 设计 — 个性化 taxonomy + 公平性(研究方向 C)

> **状态**:W5 设计定稿候选 · 待 review
> **来源**:[`11-research-roadmap.md`](11-research-roadmap.md) §4(方向 C)
> **复用**:A 的 embedding 基础设施([`12-rag-calibration-design.md`](12-rag-calibration-design.md))—— `common/embeddings.py`、指纹向量缓存、`eval` 校准框架。
> **对应 PDF**:Functional req 3(personalized recommendation engine)、page 24(profile-based models)、"avoid discriminatory inference / opt out"。

---

## 1. 背景与目标

当前个性化是**分散的手工 rubric**:
- `agents/navigator/engine.py::derive_user_skills` —— if-else 把 proficiency/work_domain 映射到 skill tag;
- `agents/comparator/engine.py::_ROLE_KEYWORDS` —— role→关键词 substring 匹配;
- `data/role_module_map.json` —— role 的 `required_skills` + 固定 `recommended_modules`。

三处各自维护、覆盖窄、易脆。且 `ConsentFlags.personalization` 字段存在但 navigator/comparator 入口**未检查**;PDF 的 "avoid discriminatory inference"、"opt out" 未落实。

本设计:
1. 统一技能定义到 curated **skill taxonomy**(对齐 ESCO/O*NET 编码)。
2. 用 **embedding 语义匹配**做"用户背景→技能"和"技能/角色→模块"(端到端语义化),复用 A 的 embedding 后端,保留**规则降级 + 可解释**。
3. 用 A 的 **eval 校准框架**确定匹配阈值。
4. **consent gate**(opt-out → 通用非个性化推荐)+ **公平性约束**(不基于 `country` 推断)。

### 非目标(YAGNI)
- 不全量集成 ESCO/O*NET(只 curated DFT 相关子集 ~30–50 技能)。
- 不引入新 embedding provider(复用 A 的配置:Ollama / OpenAI 兼容)。
- 不改 #4 Checklist 的国籍→语言证明规则(那是**官方合规规则**,非个性化推断,不在公平性约束范围)。

---

## 2. 架构总览

```
              UserProfile
                  │
     ┌────────────▼─────────────┐  consent.personalization == False
     │  consent gate (入口)       │ ────────────────────────────► 通用非个性化推荐
     └────────────┬─────────────┘                                  (role 通用模块, 无 skill-gap)
                  │ True
     ┌────────────▼─────────────┐
     │ background_text 构造       │  显式排除敏感字段 country
     └────────────┬─────────────┘
                  ▼
     ┌──────────────────────────┐      get_skill_matcher() 工厂
     │  SkillMatcher              │ ──────────┬──────────────┐
     │  ① 背景→技能               │           ▼              ▼
     │  ② 技能/角色→模块          │   EmbeddingSkillMatcher  RuleSkillMatcher
     └────────────┬─────────────┘   (cosine + 阈值)        (taxonomy.rule_hints / 固定列表)
                  ▼ (skill/module, score, 来源)
     navigator / comparator 输出(可解释)

  data/skill_taxonomy.json   ── curated 技能子集(ESCO/O*NET 编码引用)
  eval/skill_calibrate.py    ── 标注集网格扫描 → data/match_thresholds.json
```

四个可独立测试的单元:taxonomy 数据 / 匹配器 / consent gate / 公平性约束。

---

## 3. 单元 1:skill taxonomy `data/skill_taxonomy.json`

curated 子集(~30–50 技能),覆盖 6 个 target role 的 `required_skills`。每条:

```jsonc
{
  "id": "risk_modeling",
  "label": "风险建模",
  "aliases": ["quantitative risk", "风险量化", "risk management"],
  "framework": { "esco": "S1.2.6", "onet": "2.B.2.i" },  // curated 引用, 注明来源
  "description": "Quantitative methods for measuring and managing financial risk.",
  "rule_hints": ["risk", "quantitative", "建模", "风险"]   // 离线规则降级用
}
```

- 统一现有三处:迁移 navigator `skill_labels`(9 个)、role `required_skills`、comparator role 关键词到此一处。
- `framework` 引用 ESCO/O*NET 编码作为权威对齐(curated,非调 API);`description` 供 embedding;`rule_hints` 供规则降级。
- 加载:`common/skill_taxonomy.py`(`SkillDef` dataclass + `load_taxonomy()`)。

---

## 4. 单元 2:embedding 语义匹配器 `common/skill_matcher.py`

### 4.1 接口(可插拔,像 A 的 `Retriever`)

```python
class SkillMatcher(Protocol):
    def infer_user_skills(self, profile, top_k=...) -> list[SkillHit]: ...      # 匹配①
    def recommend_modules(self, role, user_skills, top_k=...) -> list[ModuleHit]: ...  # 匹配②

# SkillHit / ModuleHit: (id, label, score, source)  —— 可解释
```

工厂 `get_skill_matcher()`:embedding 可用 → `EmbeddingSkillMatcher`,否则 `RuleSkillMatcher`(降级,运行期失败也降级)。

### 4.2 `EmbeddingSkillMatcher`(主)

- **匹配① 背景→技能**:`background_text(profile)`(下文,**排除 country**)→ `embed_texts` → 对 taxonomy 技能向量算 cosine → `score ≥ skill_threshold` 的为用户技能。
- **匹配② 技能/角色→模块**:role `required_skills` + 用户技能的 label/description 拼成 query → 对 module 向量(来自 `module_catalog` 的 name+description)算 cosine → `score ≥ module_threshold` 排序推荐。
- **向量缓存** `data/_skill_vectors.json`(指纹 by model,gitignore):taxonomy 技能 + module 描述一次性 embed 缓存,复用 A 的指纹失效逻辑。
- **可解释**:每个 hit 带 score + 命中的 taxonomy/module 来源。

### 4.3 `RuleSkillMatcher`(降级)

- 匹配①:沿用现 `derive_user_skills` 逻辑,但改读 taxonomy 的 `rule_hints`(统一数据源)。
- 匹配②:沿用 `role_module_map.json` 固定 `recommended_modules`。
- 纯确定性、离线。

### 4.4 阈值校准(复用 A 的 eval 框架)

- 标注集 `eval/cases/skill_match.json`:profile → 期望 user-skill id 集合(金标,按背景独立推断)。`module_match.json`:profile+role → 期望 module 集合。
- `eval/skill_calibrate.py`:网格扫描 `skill_threshold` / `module_threshold` → 复用 `eval/metrics.set_prf` 算 P/R/F1 → 选最优(中位稳健,像 A)。入口 `python -m eval.skill_calibrate [--json]`。
- 产出写 `data/match_thresholds.json`(按后端分节,像 A 的 `thresholds.json`);`SkillMatcher` 读取(缺省回退经验值)。

---

## 5. 单元 3:consent gate

`navigator.handle` / `comparator.handle` 入口:

```
if not profile.consent_flags.personalization:
    → 通用非个性化路径:返回该 role 的通用模块列表 + 通用说明,
      不做 skill-gap / 个性化排序 / 背景推断。
```

落实 PDF "opt out of personalization"。通用路径仍有用(给 role 的标准模块),而非拒绝服务。

---

## 6. 单元 4:公平性约束

- **敏感字段**:`country`(国籍)。
- **强制点**:`background_text(profile)` 构造时**显式排除 country**;规则路径 `derive_user_skills` 现状已不读 country(确认合规)。
- **不变量测试** `tests/test_fairness.py`:构造仅 `country` 不同的两个 profile → `infer_user_skills` 与 `recommend_modules` 结果(及最终 navigator/comparator data)**必须完全相同**。embedding 与规则两后端都测。
- **边界说明**:#4 Checklist 的"国籍→语言证明"是官方合规规则,不受此约束(已在 §1 非目标声明)。

---

## 7. 测试策略(TDD)

| 测试 | 覆盖 |
|---|---|
| `tests/test_skill_taxonomy.py` | 加载、字段、覆盖 6 role 的 required_skills |
| `tests/test_skill_matcher.py` | 桩 embedder 确定性:背景→技能排序、技能→模块排序、缓存指纹失效、工厂降级 |
| `tests/test_skill_calibrate.py` | 网格扫描产出最优阈值、指标计算 |
| `tests/test_consent_gate.py` | personalization False → 通用路径(无 skill-gap) |
| `tests/test_fairness.py` | 仅 country 不同 → 推导/推荐不变(两后端) |
| 现有 navigator/comparator 测试 | 不回归 |

conftest 隔离凭据 → 套件离线走 `RuleSkillMatcher`,确定;真实 embedding 匹配为 `skip if not configured` 冒烟测试。

---

## 8. 分阶段实现

1. **阶段 1(taxonomy + 规则降级,离线)**:`skill_taxonomy.json` + `common/skill_taxonomy.py` + `RuleSkillMatcher` + `get_skill_matcher()` 工厂(降级)+ 测试。
2. **阶段 2(embedding 匹配器)**:`EmbeddingSkillMatcher` + 向量缓存(指纹)+ 桩/冒烟测试。
3. **阶段 3(校准)**:标注集 + `eval/skill_calibrate.py` + `data/match_thresholds.json` + matcher 读取。
4. **阶段 4(consent + 公平性 + 接入)**:consent gate + 公平性约束 + 不变量测试 + 接入 navigator/comparator + 文档。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| taxonomy 子集主观/覆盖不全 | 先覆盖 6 role 的 required_skills;ESCO/O*NET 编码作权威锚;后续可扩 |
| embedding 匹配不确定,污染"裁决归规则" | 匹配只做**召回+排序**,阈值由校准定、可解释;最终输出带 score+来源;离线降级确定 |
| embedding 分数分布与 A 的 RAG 不同 | 独立校准 `match_thresholds.json`,不复用 RAG 阈值 |
| 公平性"仅 country"可能不足 | 本期锁 country(用户决定);taxonomy/背景文本结构留扩展位,后续可加字段 |
| ESCO/O*NET 编码 curated 易错 | 注明 curated + 来源;编码仅作引用展示,不影响匹配逻辑(匹配靠 description embedding) |
| 测试依赖 Ollama | conftest 隔离 → 离线走 RuleSkillMatcher;embedding 匹配仅冒烟 skip |
