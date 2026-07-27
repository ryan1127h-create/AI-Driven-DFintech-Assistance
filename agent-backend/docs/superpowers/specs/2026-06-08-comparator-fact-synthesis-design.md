# 设计 — Comparator v3:多维对比 + fact/synthesis 分离(研究方向 D)

> **状态**:已确认(brainstorm 2026-06-08)· 待写实现计划
> **范围**:#6 Comparator(`agents/comparator/{engine,agent}.py` + `data/programs_dataset.json` + 配套契约/refresh/admin/student/tests)
> **前置**:Comparator v2(`docs/09-comparator-v2-design.md`)已落地:5 所真实项目、7 展示维度、`derive_role_strengths` 可辩护推导、按用户权重加权评分(role_fit/cost/duration)、consent gate。
> **合规基线不变**:`disclaimer` 恒在;narrative 不生成排名;每项带来源(`source_url`/`fetched_at`)。

---

## 1. 背景与问题

PDF「5. Program comparison capability」有两条硬要求,v2 尚未满足:

1. **Distinguish verified facts from AI-generated synthesis** —— 当前 `ComparisonRow` 把事实(`values`)与派生信号(`weighted_score`/`matched_roles`)混在一起,UI/数据层没有显式 fact↔synthesis 边界。
2. **Avoid unsupported ranking claims** —— 当前唯一护栏是 LLM system prompt,无确定性强制。

同时 PDF 列出的对比维度(curriculum focus / delivery format / duration / typical applicant profile / industry orientation / technical depth / career pathways / fees & scholarship)中,`typical_profile / industry_orientation / technical_depth / career_pathways` 四项尚未进入数据。

### 1.1 关键设计判断(已与用户确认)

「维度」有两个不同概念,**不可混为一谈**:

| 概念 | 是什么 | v2 现状 |
|------|--------|---------|
| **展示维度** | 对比表里展示的事实字符串 | 7 个 |
| **评分维度** | 喂给 `weighted_score` 的 0–1 *fit* 信号 | 3 个(role_fit/cost/duration) |

判据:**一个维度能否在不变成主观意见的前提下被打成 0–1 分?**
- 可客观解析 → 可评分:`duration`(解析月数)、`fees/cost`(解析金额)、`role_fit`(课程关键词 ∩ 目标岗位)。
- 主观 → 一打分即制造排名:`technical_depth`(无可辩护的 0.7)、`typical_profile`(描述非量级)、`industry_orientation`(有无实习是事实 yes/no)、`career_pathways`(岗位列表,且与 role_fit 重叠)。

**结论**:D 扩展的是**展示维度**(到 PDF 的 8 个),**评分维度保持 3 个不变**。给主观维度打数值分恰恰违反「avoid unsupported ranking claims」。D 的真正价值在 fact/synthesis 的结构化分离与防排名强制。

---

## 2. 数据模型(D-1 + D-2)

### 2.1 三态 cell

每个对比单元从裸字符串升级为带类型与来源的结构,`kind` 三态直接对应 PDF 答案分级:

| kind | 含义 | 进评分? | UI 区域 |
|------|------|---------|---------|
| `verified` | 官方源直接核验的事实(如 "S$74,120") | ✅ 可 | 事实表 |
| `unknown` | 官方未公开 / 需自查 | ❌ 中性 0.5 | 事实表(灰显) |
| `synthesis` | 编辑/AI 的定性解读(主观维度) | ❌ 永不 | AI 综合区 |

```jsonc
"fees":           { "text": "S$74,120 ...", "kind": "verified" },
"intake":         { "text": "请见 NTU 官方页", "kind": "unknown" },
"technical_depth":{ "text": "CS/AI 核心强,含区块链/ML", "kind": "synthesis" }
```

- **来源**:`verified` cell 的 `source_url`/`fetched_at` 默认继承 row 级;cell 可自带覆盖。
- **向后兼容(必须)**:loader 把裸字符串规范化为 `{text, kind:"verified", source_url:行级, fetched_at:行级}`。旧数据不报废,可逐步补 `kind`。
- **规范化是 loader 唯一入口**,engine 其余逻辑只面对规范化后的对象,不处理「字符串或对象」的二义。

### 2.2 展示维度扩到 8

在 v2 的 7 维基础上**新增 4 个**(默认 `kind:"synthesis"`,有官方依据时可标 `verified`):
`typical_profile`、`industry_orientation`、`technical_depth`、`career_pathways`。

现有 `curriculum_focus / duration / format / fees / intake / scholarship / gmat_gre` 全部保留(PDF 措辞为 "such as",非封顶)。`dimensions` 数组相应更新;缺数据的维度按 `unknown` 如实标注,不留空。

---

## 3. engine 输出结构分离(D-3)

`compare()` 的每行从「facts 与 score 混在 `values`」改为**结构两分**:

```python
@dataclass
class ComparisonRow:
    program: str
    is_target: bool
    facts: dict[str, FactCell]      # {dim: {text, kind, source_url, fetched_at}}
    synthesis: RowSynthesis         # matched_roles / role_reasons / weighted_score / score_breakdown

@dataclass
class FactCell:
    text: str
    kind: str                       # verified | unknown | synthesis
    source_url: str | None = None
    fetched_at: str | None = None

@dataclass
class RowSynthesis:
    matched_roles: list[str]
    role_reasons: dict[str, list[str]]
    weighted_score: float
    score_breakdown: dict[str, float]
```

`Comparison` 顶层:`dimensions`、`rows`、`disclaimer`、`best_for_you`(synthesis)、`weights`。

### 3.1 硬不变量(可测试)

- **评分只读 `kind=="verified"` 的 cell**。fees 为 `unknown` → cost 中性 0.5(沿用现有 `_inverse_minmax` 的 None→0.5);任何 `synthesis` cell 永不参与任何分数。
- fit 分仍只来自 `role_fit / cost / duration` 三个信号。`role_fit` 从 `curriculum_focus`(须 verified)推导。
- `best_for_you` 仍为最高加权分(并列偏向 target);属 synthesis。

---

## 4. 防排名护栏(D-4)

从「靠 prompt」升级为「确定性强制」。新增纯函数:

```python
def violates_ranking(text: str) -> bool:
    """命中跨项目排名措辞即 True。"""
```

- **封禁**(中英,跨项目排名):`优于`、`更好`、`胜过`、`排名`、`第一`、`最好的(项目|项目是)`、`better than`、`best (program|programme|option|choice)`、`outperform(s)`、`superior to`、`#1`、`ranked`、`top program(me)`。
- **允许**(贴合度表述,不得误伤):`best fit for you`、`最适合你的目标`、`贴合你的目标`。
- 流程:LLM narrative 生成后过 `violates_ranking`;命中即丢弃、回退安全模板(现有 `fallback`)。
- 测试双向:封禁样本必触发回退;允许样本必通过。

---

## 5. agent / envelope + 学生页(D-3 落到 UI)

### 5.1 envelope

`AgentResponse.data` 显式分区(更新契约 `docs/02-interface-contracts.md §4 #6`):

```jsonc
{
  "dimensions": [...],
  "facts_table": {                       // 全部展示维度,每格带 kind(verified/unknown 带来源;synthesis 不带)
    "rows": [ { "program": "...", "is_target": true,
               "facts": { "fees": {"text":"...","kind":"verified","source_url":"...","fetched_at":"..."} } } ]
  },
  "synthesis": {                         // 派生/AI(关闭个性化时整体抑制)
    "rows": [ { "program": "...", "matched_roles":[...], "role_reasons":{...},
                "weighted_score": 0.0, "score_breakdown": {...} } ],
    "best_for_you": "NUS ...",
    "narrative": "...",
    "weights": {...}
  },
  "disclaimer": "...",                    // 恒在
  "personalized": true
}
```

`answer_type` 顶层仍为 `advisory`;fact/synthesis 边界落在 `data` 内部。

### 5.2 学生结果页

对比区按现有模板风格做**最小改动**:
- 事实表:每格显示文本 + 来源链接;`unknown` 灰显标「未公开」。
- fit 分 + best_for_you + narrative 收入视觉独立的「**AI 综合分析(非官方事实)**」块。
- consent gate 不变:`personalization=False` → 只渲染事实表,整个 synthesis 块抑制。

---

## 6. 配套:refresh / admin / 测试

### 6.1 refresh / admin schema

`programs_dataset` 为 `trusted=false`(永远强制人工审核)。需更新其 schema/校验以接受:
- cell 的对象结构(`{text, kind, source_url?, fetched_at?}`)与裸字符串(兼容)。
- 4 个新维度。
- `synthesis` cell 由研究步起草、仍走人工确认(已被 trusted=false 强制,无需额外门)。
- 具体文件(refresh 侧 schema、admin 侧 `admin/schemas.py` 的 programs_dataset 模型)在 plan 阶段逐一定位确认。

### 6.2 测试

- loader:裸字符串→`verified` 规范化;来源继承 row 级。
- 每格 `kind`/源透传正确。
- **评分只吃 verified**:fees=unknown → cost=0.5;synthesis cell 不影响任何分数(关键不变量)。
- engine 输出 facts/synthesis 结构两分。
- 防排名护栏双向(封禁触发回退;允许通过)。
- consent gate:opt-out → synthesis 抑制、事实表仍在。
- **回归**:现有 comparator 测试 + `eval.runner` 12/12 不破。

---

## 7. 文件清单(预期触点)

| 文件 | 改动 |
|------|------|
| `data/programs_dataset.json` | 新增 4 维;关键 cell 升级为三态对象;unknown 如实标注 |
| `agents/comparator/engine.py` | `Comparison`/`ComparisonRow`/`FactCell`/`RowSynthesis` 重构;loader 规范化;评分只读 verified;`violates_ranking` |
| `agents/comparator/agent.py` | envelope 两分区;narrative 过护栏 |
| `docs/02-interface-contracts.md` | §4 #6 data 形状更新 |
| `docs/09-comparator-v2-design.md` | 标注被本 v3 spec 取代/补充 |
| refresh / admin schema | 接受三态 cell + 新维度(plan 阶段定位) |
| `student/` 对比模板 | 事实表 + AI 综合区两分渲染 |
| `tests/` | 上述新增 + 回归 |

---

## 8. 非目标(YAGNI)

- **不**给主观维度(technical_depth 等)做数值评分。
- **不**新增对比项目(项目集沿用 v2 的 5 所)。
- **不**改 RAG/检索或 confidence 门控(那是方向 A,已落地)。
- **不**做真实招生 API 对接(future work)。
