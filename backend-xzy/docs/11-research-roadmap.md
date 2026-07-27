# 研究路线图 — #4–#7 下一步深化方向

> **状态**:W3 候选 · 由 #4–#7 负责人维护
> **目的**:把"现状(确定性规则 + LLM 叙述,可运行/可测)"升级为"可检索、可度量、可校准"的系统,补上 PDF 需求里反复强调但目前**接口预留 / 写死 / 未度量**的几块。
> **配套**:契约见 [`02-interface-contracts.md`](02-interface-contracts.md);各模块 v2 设计见 `07`–`10`。

---

## 0. 现状基线(已完成,作为本路线图的起点)

| 模块 | 已实现 | 证据 |
|------|--------|------|
| #4 Checklist | base+conditional 规则项、富文档状态、deadline/urgency 分桶、`unknown_condition`→escalation | `agents/checklist/engine.py` |
| #5 Tracker | mock 状态机+翻译+eta、timeline、里程碑提醒(consent/channel/frequency/去重) | `agents/tracker/` |
| #6 Comparator | 可解释 role 强度推导、加权评分(role_fit/cost/duration)、合规 disclaimer、来源 url | `agents/comparator/engine.py` |
| #7 Navigator | role→module、技能差距、prereq 树评估、毕业学分进度、full/part-time 排课、overload、what-if | `agents/navigator/` |
| 横切 | 生命周期分流、RAG 置信门控(三级)、统一 envelope、LLM 降级、admin 录入、refresh 真实数据 | `supervisor.py` / `common/confidence.py` |

**判断**:工程层已完整。真正的差距集中在下面四个方向,且它们**有依赖关系**,不是并列。

---

## 1. 方向依赖关系(执行顺序)

```
        ┌─────────────────────────────────────────────┐
        │  B. 评估框架(底座:标注集 + 指标 + harness)   │
        └───────────┬───────────────────┬─────────────┘
                    │                   │
        ┌───────────▼──────┐    ┌───────▼──────────────┐
        │ A. RAG + 阈值校准 │    │ C / D 复用 B 的指标   │
        │ (需要 B 的标注集) │    │ 验证改进是否真有收益   │
        └──────────────────┘    └──────────────────────┘
```

**B 必须先做**:没有评估集和指标,A 的"阈值校准"无从校准,C/D 的"改进"也无法证明有效。
推荐节奏:**B 打地基 → A 用它校准 → C/D 各自用它验证收益**。

---

## 2. B — 推荐/对比质量评估框架(底座,优先级 P0)

- **问题定义**:把 PDF Acceptance Criteria("recommend relevant courses""generate personalized checklist""answer accurately")从口号变成**可度量数字**。当前只有规则引擎单测(正确性断言),**没有质量度量**。
- **数据/标注**(`eval/cases/`):每个 agent 一个小而真的标注集,期望值由"需求/persona 常识"独立写出(不照搬规则逻辑,避免自证),用真实输出来核对、暴露规则缺陷。
  - #4:profile → `must_include` / `must_exclude` 清单项 + 关键项期望 `status` + `outstanding` 下限。重点覆盖 conditional 分支(如 `english_proficiency` 的豁免对照)。
  - #7:profile+role → 期望 `skill_gaps`(skill tag 集合) + 推荐模块是否属于该 role 金标集合。
- **方法**:
  - 规则类(#4/#5/#7 裁决)→ 确定性集合比对(precision/recall/F1/Jaccard)。
  - 主观类(#6 narrative / #7 explanation)→ **LLM-as-judge**(给 rubric,DeepSeek 打分),复用 `common/llm.py` 降级机制保证离线可跑。**本阶段先做裁决类,LLM-judge 为下一步**。
- **指标**:
  - #4:`required_recall`(必需项召回)、`exclusion_precision`(条件项误增率的反面)、`status_accuracy`。
  - #7:`skill_gap` 集合的 precision/recall/F1、`module_relevance`(推荐∈role 金标)。
- **代码改动点**:新增 `eval/metrics.py`(纯函数)、`eval/runner.py`、`eval/cases/*.json`;可套已装的 ECC `/eval-harness`、`/test-coverage`。
- **产出**:一张随每次改动可重跑的"质量记分卡"(human + JSON),capstone 报告里最硬的量化证据。
- **本仓已落地**:见 §6「已实现的最小版」。

## 3. A — RAG 检索 + 阈值校准(核心,P0,B 之后)

- **问题定义**:`common/confidence.py` 目前是"空门控"——无真实知识库;`answer_type`(official/advisory/recommendation)按 intent **硬编码**;三个阈值 `0.60 / 0.72 / 0.80` 拍脑袋。
- **方法**:
  1. 建 curated 知识库:NUS DFT 招生/课程/政策页切块 → `data/knowledge/*.jsonl`,每块带 `source_id` + `namespace`(对齐契约 §3)。
  2. 接 embedding 检索(本地 sentence-transformers 或 DeepSeek embedding),做成**可插拔后端**(参照 `refresh/` 的 `Fetcher` 接口),保留 `_lexical_similarity` 作离线降级。
  3. **来源驱动的 answer 分级**:从命中来源类型推断 `answer_type`,替代 intent 写死。
  4. **阈值校准**:用 B 的标注集 + 一组"该答/该追问/该转人工"的标注查询,扫阈值画 precision-recall / 校准曲线(ECE),选最优。← 可写论文的量化部分。
- **代码改动点**:`common/confidence.py`、`supervisor._maybe_apply_confidence_gate`、新增 `common/retriever.py`。
- **产出**:校准曲线 + 最优阈值表 + 端到端 source attribution。对应 PDF req 4 / page 25。

**状态:已落地(W4)**

## 4. C — 个性化 taxonomy + 公平性(专项,P1)

- **问题定义**:`derive_user_skills` / `_ROLE_KEYWORDS` 是窄手工 rubric(覆盖少、易脆);`consent_flags.personalization` 字段存在但推荐时**未真正 gate**;PDF 的 "avoid discriminatory inference""opt out" 未落实。
- **方法**:skill 词表升级为对齐行业框架(ESCO / O*NET)的 **taxonomy**;role–module–skill 改嵌入式匹配;入口加 `if not consent.personalization: 走通用非个性化路径`;加"不基于国籍/年龄等敏感字段推断"的约束测试。
- **代码改动点**:`data/skill_taxonomy.json`、`agents/navigator/engine.py`、各 agent 入口 consent gate、`tests/test_fairness.py`。
- **产出**:taxonomy 覆盖率提升 + 公平性约束可测断言。对应 req 3 / page 24。

**状态:已落地(W5)** —— `data/skill_taxonomy.json`(9 核心技能,ESCO/O*NET 编码引用)+ `common/skill_matcher.py`(可插拔:`EmbeddingSkillMatcher` 语义匹配 / `RuleSkillMatcher` 降级,按后端 `data/match_thresholds.json` 校准)+ navigator/comparator consent gate(opt-out → 通用推荐)+ 公平性(background_text 排除 country + 不变量测试)。**实证:背景→技能匹配 规则 f1=1.0 vs embedding 0.685**,再次印证精确映射上规则更可靠。

## 5. D — #6 多维对比 + fact/synthesis 分离(专项,P1)

- **问题定义**:评分只用 3 维(role_fit/cost/duration),PDF page 10 要 8 维(`technical_depth` / `typical_profile` / `industry_orientation` / `career_pathways`… 数据里有但没进评分);narrative **没显式标注**哪些是 verified fact、哪些是 AI synthesis(PDF 硬要求)。
- **方法**:更多维度纳入可解释评分(保持"裁决归规则");`data` 层给每个对比单元打 `verified: true/false` + `source_url`,UI 与 narrative 显式分区;narrative 用受约束模板防止生成排名。
- **代码改动点**:`agents/comparator/engine.py`、`data/programs_dataset.json`、`student/templates/results.html`。
- **产出**:8 维可解释对比 + 可审计的事实/综合分离。

---

## 6. 已实现的最小版(B,W3)

首批落地 B 的骨架,作为 A/C/D 的验证工具:

```
eval/
  metrics.py        # 纯函数:集合 precision/recall/F1
  runner.py         # 读 cases → 跑 engine(确定性,不走 LLM)→ 算指标 → 记分卡
  cases/
    checklist.json  # #4 标注集
    navigator.json  # #7 标注集
```

运行:

```bash
python -m eval.runner            # 人类可读记分卡
python -m eval.runner --json     # 机器可读(用于回归/对比)
```

**设计原则**:评估的是"裁决"质量,直接调 engine 层(`build_checklist` / `guide_for_role`),纯确定性、可复现、离线可跑;LLM 叙述质量(LLM-as-judge)为下一步。

---

## 7. 里程碑

| 阶段 | 内容 | 状态 |
|------|------|------|
| W3 | B 最小版(裁决类记分卡:#4 + #7) | ✅ 本次 |
| W4 | B 扩展(#6 公允性检查 + LLM-as-judge);A 知识库切块 + 检索后端 | ✅ 已落地(检索骨架 `BM25Retriever`、`EmbeddingRetriever`、`get_retriever()` 工厂与阈值校准均已实现) |
| W5 | A 阈值校准(标注查询集 + 校准曲线) | ✅ 已落地(`eval/calibrate.py` 网格扫描 → `data/thresholds.json`,best low=0.15/clar=0.30/strict=0.55,acc=1.0) |
| W6 | C taxonomy + consent gate;D 多维对比 + fact/synthesis 分离 | ✅ C 已落地(taxonomy + 可插拔 SkillMatcher + consent gate + 公平性 + 按后端校准);D 待做 |

## 8. 风险与对策

- **金标主观性**:标注集小、易引入偏见 → 多人交叉标注 + 记录标注准则;先覆盖确定性强的分支。
- **LLM-judge 不稳定**:打分波动 → 固定 rubric + 温度 0 + 多次取中位;离线降级时跳过 judge 类指标。
- **阈值过拟合标注集**:校准集与测试集分离,报告留出集指标。
</content>
