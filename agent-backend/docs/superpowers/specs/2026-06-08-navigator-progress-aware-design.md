# 设计 — Navigator 进度感知 + LLM 受约束选课(#7)

> **状态**:已确认(brainstorm 2026-06-08)· 待写实现计划
> **范围**:#7 Navigator(`agents/navigator/{engine,agent,planner}.py` + 新 `data/module_skills.json` + `supervisor.py` + 配套数据/测试/文档)
> **前置**:Navigator v2(`docs/10-navigator-v2-design.md`)已落地:role→模块(catalog 富化)、SkillMatcher 技能缺口、planner(先修/毕业学分/full-part-time 排课)、consent gate + 公平性(排除 country)不变量。`UserProfile.completed_modules` 已存在,**由学生在确认表单手填**(`student/profile_form.py`,逗号/分号分隔;申请者可留空)。
> **架构基线**:裁决归规则,LLM **受约束**参与;离线可测(无 key → 确定性兜底);consent opt-out → 无个性化缺口;公平性不涉及 country。

---

## 1. 目标与关键决定

把 #7 从「岗位 → 固定推荐表 + LLM 只写解释」升级为**进度感知 + 缺口驱动 + LLM 受约束挑选**的推荐引擎,并区分选课/职业两个意图。

**五块 + 一个新推荐内核(brainstorm 已确认)**:
- **A** 推荐对已修做出反应(排除/标注已修)
- **B** 毕业进度修正 + 计划只排剩余
- **C** 区分 `recommend_courses` / `recommend_career_path`
- **D** 已修 → 反推技能(新数据 `module_skills.json`)
- **E** 已修代码校验软提醒(数据质量)
- **F** 推荐内核:**规则出候选 → LLM 受约束挑选 → 校验 → 确定性兜底**

**数据决定**:`module_skills.json`(模块→技能)为人工编辑、独立文件,**不混进**自动刷新的 `module_catalog.json`;一份数据两用——既做 D(已修→技能),又做 F(缺口→候选课)。

---

## 2. 推荐内核 F(总流程)

```
目标岗位 ──▶ ① 规则建候选池(确定性) ──▶ ② LLM 在候选内挑选/排序+理由
                                          │
                                          ▼
                              ③ 校验:非候选(编造)→ 丢弃;全无效 → 回退①排序
                                          │
                                          ▼
                              ④ 兜底:无 key/离线/测试 → 纯规则排序取 top N
```

### 2.1 ① 候选池构建(规则,确定性)— `engine.build_candidates(profile, role)`
- **技能集**:`have = matcher.infer_user_skills(profile) ∪ skills_from_completed(profile.completed_modules)`(D);`gaps = role.required_skills − have`。
- **候选来源**:`岗位策划模块(role_module_map,始终纳入)` ∪ `module_skills.json 中 skills ∩ (role.required_skills ∪ gaps) ≠ ∅ 的模块`(这些都是我们策划过的真实 NUS 代码)。
- **过滤**:**只排除 `completed_modules`**(A)。**不**以「是否在 `module_catalog`」做硬过滤——目录是 NUSMods 子集,可能漏收策划过的真课;改为用 `verified` 标记是否在目录中(供 UI/审计区分),不在目录的退回 role_map 名称(沿用现有 `_enrich_modules` 行为)。
- **每个候选 `Candidate` 标注**:`code, name, credits, skills(来自 module_skills), closes_gaps(skills ∩ gaps), prereq_ok+missing(planner), verified(是否在目录中), source("role"|"gap")`。

### 2.2 ② + ④ 选择器 — `engine.select_modules(candidates, gaps, n=4)`
- **确定性排序(兜底)** `rank_candidates`:按 `(closes_gaps 数量 desc, source=role 优先, credits asc, code)` 排序,取前 `n`。
- **LLM 受约束挑选**(`llm.available()` 时):把候选清单(code/name/skills/closes_gaps/credits)喂给 LLM,要求**只从给定 code 中**返回有序短名单 + 每门理由 + 总体说明;解析输出。
- **无 key / 离线 / 测试** → 直接用确定性排序结果 + 模板说明。

### 2.3 ③ 校验护栏(必做)
- LLM 返回的 code **逐一校验 ∈ 候选 code 集**;不在的(编造/已修/无效)**丢弃**;保序。
- 若校验后为空 → **回退**确定性排序结果。
- 与 #6 narrative 防排名护栏同一套「LLM 输出经规则校验」思路。**绝不输出不存在的课**。

**效果**:推荐随个人技能缺口变化、有理由、且永不编课;无 key 也能用、测试稳定可复现可审计。

---

## 3. A — 推荐对已修做出反应
已并入候选构建(§2.1 过滤 `completed_modules`)。此外:
- `RoleGuidance`/返回数据保留 `already_completed`(已修且属岗位推荐或候选的模块,标 `completed=True`),供 UI 显示「✓已修」。
- **效果**:在校生看「接下来该选什么」,已修标✓不重复;申请者(空已修)→ 候选不被过滤,行为接近现状。

## 4. B — 毕业进度修正 + 计划只排剩余
- `agent` 传给 planner 的是**选中的待修 codes**(`selected`),而非旧的固定全量。
- `planner.graduation_progress(completed, selected_codes)`:`planned` 只计 `code not in completed`(双保险,不重复计)。
- `what_if_pathways(selected_codes)` 只排选中的待修模块。
- **效果**:学分进度准确(已修 N + 待修 M,不重复);课表只显示要上的课。

## 5. C — 区分选课 vs 职业路径
- `agent.career(profile, slots)`(新):职业视角。复用候选/缺口;`data` 以「岗位 → 必需技能 → 已具备(matched,含已修课程贡献)/缺口 → 补缺口的选中模块(`gap_closing_modules`)」为主;**不含** `study_plans`/`prereq_warnings`(弱化排课)。
- `agent.handle`(选课视角)保留并升级:选中待修模块 + 学期计划 + 先修警告 + 毕业进度。
- `supervisor._ROUTES`:`recommend_career_path` → `("agents.navigator.agent","career")`;`recommend_courses` → `handle`。
- 两者都过 §2 的选择器 + 护栏;`career` 的「补缺口模块」也来自校验后的候选。
- **效果**:问「选什么课」给课表;问「职业路径」给岗位-技能-补缺口分析。

## 6. D — 已修 → 反推技能(新数据)
### 6.1 `data/module_skills.json`
```jsonc
{
  "_comment": "人工编辑 模块代码->技能标签;标签须在 role_module_map.skill_labels(9个)内;独立于自动刷新的 module_catalog。",
  "modules": { "BMS5312": ["product","finance"], "FT5005": ["ai_ml","programming","finance"] /* …role_map 涉及模块全填 */ }
}
```
- 合法标签 = `programming/data_analytics/finance/risk_modeling/product/regulation/payments_systems/security/ai_ml`;未知标签忽略;文件缺失 → 降级为「无额外技能/无缺口候选」,不报错。
- 实现方按 9 词表给 `role_module_map` 涉及模块填一版 seed。

### 6.2 engine 接入
- `skills_from_completed(completed) -> set[str]`:聚合已修模块的合法技能标签。
- 喂给 §2.1 的 `have` 并集 → 缩小 `gaps`、并丰富 §2.1 候选来源。
- `RoleGuidance` 可透出 `skills_from_courses`(哪些技能来自已修课程)。
- **效果**:已修课证明的技能被认可,缺口更准、不让学生补已会的。

## 7. E — 已修代码校验软提醒(数据质量)
- `engine.unrecognized_completed(completed) -> list[str]`:不在「`module_catalog` ∪ `role_module_map` 代码」中的已修代码(大小写归一)。
- `handle`/`career` 的 `data` 加 `unrecognized_completed`;学生页显示**软提醒**:「以下已修代码未在课程库中找到(可能拼写有误或暂未收录),请核对:…」。
- 措辞为「请核对」非「错误」(目录是 NUSMods 子集,可能漏收真课);不阻断、不丢弃(未知代码仍按未知处理)。
- **效果**:学生看到填错/无法识别的代码被指出,可改正,避免「填了却没生效」。

---

## 8. Envelope / 渲染
- `recommend_courses`(handle)`data`:`target_role`、`recommended`(选中待修模块,每项 `code/name/credits/skills/closes_gaps/reason/verified/source`)、`already_completed`、`candidate_count`、`skill_gaps`、`prereq_warnings`、`graduation_progress`、`study_plans`、`unrecognized_completed`、`explanation`、`selection_source`(`"llm"|"rule"`)、`personalized`。
- `recommend_career_path`(career)`data`:`target_role`、`required_skills`、`matched_skills`、`skills_from_courses`、`skill_gaps`、`gap_closing_modules`(选中,带 closes_gaps/reason)、`unrecognized_completed`、`explanation`、`selection_source`、`personalized`。
- `selection_source` 让 UI/审计看出这次是 LLM 挑的还是规则兜底。
- 学生页 `results.html` #7 区:已修标✓、课表只剩待修、显示每门「补什么缺口 + 理由」、`unrecognized_completed` 软提醒。
- 契约 `docs/02-interface-contracts.md §4#7` 更新两个意图 data 形状(并标注 LLM 受约束 + 校验 + 兜底)。

## 9. 数据 / 演示
- `common/mock_data.py`:在读学生 demo 设 `completed_modules` 含某岗位候选里的 1–2 模块(演示 A/B/D),并含 1 个故意拼错的代码(演示 E)。
- `run.py courses/career`:确认两条命令输出不同;无 key 时显示 `selection_source=rule`。

## 10. 测试(`tests/test_navigator.py` + `tests/test_navigator_planner.py`)
全离线确定性(LLM 一律 mock 或走兜底):
- **候选(F①)**:候选来自 role∪gap、在目录中、排除已修;每项带 closes_gaps/prereq/skills/source。
- **确定性排序(F④)**:`rank_candidates` 按 closes_gaps→role优先→credits 稳定排序;无 key/离线 → `selection_source="rule"`。
- **LLM 校验(F③)**:mock `llm.explain`/选择器返回「合法 code + 编造 code + 已修 code」→ 只保留合法候选、保序、`selection_source="llm"`;返回全无效 → 回退规则、`selection_source="rule"`。
- **A**:已修不在 `recommended`、出现在 `already_completed`;空已修 → 不过滤。
- **B**:`graduation_progress` 不重复计;`study_plans` 不含已修;planned 双保险。
- **C**:`career` 含 required/matched/gaps/gap_closing_modules、**不含** study_plans;`handle` 含 study_plans;supervisor `recommend_career_path`→`career`(route 验证输出不同)。
- **D**:`skills_from_completed` 聚合合法/忽略未知/缺文件空;已修映射到某 required_skill → 该技能从 gaps 移到 matched;consent off → 不展示 gaps。
- **E**:`unrecognized_completed` 列出未知代码、识别的不列、空→空;不影响流程。
- **回归**:现有 navigator/planner 测试 + `eval.runner`(navigator cases)**;eval cases 若断言旧固定推荐形状,迁移到 `recommended`/候选形状(金标仍按规则独立推断,LLM 关闭)。**

---

## 11. 文件清单
| 文件 | 改动 |
|------|------|
| `data/module_skills.json` | 新:模块→技能 seed |
| `agents/navigator/engine.py` | `skills_from_completed`、`unrecognized_completed`、`build_candidates`、`rank_candidates`、`select_modules`(LLM 受约束 + 校验 + 兜底)、`have` 并集、`RoleGuidance` 字段 |
| `agents/navigator/planner.py` | `graduation_progress` planned 排除已修(双保险) |
| `agents/navigator/agent.py` | `handle` 走候选→选择器→排课(选中待修);新 `career` handler;`selection_source` |
| `supervisor.py` | `recommend_career_path` → `navigator.agent.career` |
| `common/mock_data.py` | 在读学生 demo:completed ∩ 候选 重叠 + 1 个拼错代码 |
| `student/templates/results.html` | #7 区:已修✓、待修课表、每门补缺口+理由、E 软提醒 |
| `docs/02-interface-contracts.md §4#7` · `docs/10-navigator-v2-design.md` | 更新 |
| `CHANGELOG.md` · `docs/00-project-overview.md` | 记录 |
| `tests/test_navigator.py` · `tests/test_navigator_planner.py` · `eval/cases/navigator.json` | 上述 + 回归/迁移 |

---

## 12. 非目标(YAGNI)
- 不让 LLM **自由**决定(只在候选池内受约束挑选 + 校验)。
- 不做实习/项目/校友匹配(#9/#10)。
- 不做官方学分换算/免修裁定(进度为参考,非官方 audit)。
- 不把 `module_skills` 接入 admin 录入工具(先静态 seed,后续可加)。
- 不改 SkillMatcher 的画像→技能推断(只在 `have` 上做并集)。
