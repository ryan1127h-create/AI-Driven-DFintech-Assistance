# 项目总览 — MSc DFT Assistant(模块 #4–#7)

> **这是项目的唯一权威入口文档。** 任何人(包括未来的我/队友/导师)想了解项目全貌,从这里开始;深入细节再点进对应的分文档。
> **维护约定**:每次代码或设计有变动,都要 ① 在 [`CHANGELOG.md`](../CHANGELOG.md) 追加一条;② 更新本文档受影响的小节(尤其 §4 现状表 与 §6 状态)。已配 hook 自动提醒(见 §8)。
> **最近更新**:2026-06-08

---

## 1. 这是什么

NUS SoC **「MSc DFT(数字金融科技硕士)申请人 AI 助手」**(FT5007 internal capstone)的一部分。整个产品是覆盖学生全生命周期(潜在申请人 → 申请人 → 录取 → 在读 → 毕业 → 校友)的 **supervisor + 专家 agent** 系统,目标是替代大部分 L1/L2 人工客服。

完整需求见桌面 PDF《AI-driven Assistant for Applicants to MSC DFT》。MVP scope 共 9 项,**本仓库负责其中第 4–7 项**:

| # | 模块 | 功能 | 入口意图 | 深化设计 |
|---|------|------|---------|---------|
| 4 | `agents/checklist` | 个性化申请材料清单 + 缺失项 | `generate_application_checklist` / `check_missing_documents` | [07](07-checklist-v2-design.md) |
| 5 | `agents/tracker` | 申请状态翻译 + 截止提醒 | `get_application_status` / `configure_reminders` | [08](08-tracker-v2-design.md) |
| 6 | `agents/comparator` | 项目客观对比 + 目标匹配叙述 | `compare_programs` | [09](09-comparator-v2-design.md) · [D spec](superpowers/specs/2026-06-08-comparator-fact-synthesis-design.md) |
| 7 | `agents/navigator` | 岗位导向选课 + 技能差距 | `recommend_courses` / `recommend_career_path` | [10](10-navigator-v2-design.md) |

---

## 2. 核心设计原则

1. **裁决归规则,叙述归 LLM**:资格/缺失/状态/推荐/对比结论由纯 Python 规则引擎确定性产出;DeepSeek 只把结果写成人话,不做判断。对应 PDF「recommendation engine = rule-based + retrieval + profile-based + human guardrails」。
2. **统一数据契约**:所有 agent 只吃 `UserProfile`([schema](01-user-profile-schema.md)),输出统一信封 `AgentResponse`([contracts](02-interface-contracts.md))。
3. **外部系统全 mock**:招生/CRM 用本地 mock,形状对齐真实 API,后期可替换。
4. **离线可跑**:未配 DeepSeek key 时 LLM 层降级为确定性模板;agent 与测试均不依赖网络。
5. **合规优先**:答案分级(official/advisory/recommendation)、来源引用、对比不排名、个性化需 consent、低置信转人工。

---

## 3. 系统架构

```
                ┌─────────────────────┐
 用户输入 ─────▶ │ 对话/意图模块(队友)  │  产出 {intent, slots, profile_ref}
                └──────────┬──────────┘
                           │ 上游契约(contracts §1)
                           ▼
        ┌──────────────────────────────────────────┐
        │  supervisor.route(intent, profile, slots)  │  生命周期分流 + RAG 置信门控
        │  #4 Checklist · #5 Tracker · #6 Cmp · #7 Nav │  每个 = agent.py(叙述) + engine.py(规则)
        └───┬───────────────────────────────┬────────┘
            │ RAG 调用(contracts §3)        │ Escalation 上报(contracts §2)
            ▼                                ▼
   ┌─────────────────┐              ┌──────────────────────┐
   │ RAG/知识模块      │              │ Escalation 模块(队友) │
   │ common/retriever │              └──────────────────────┘
   └─────────────────┘
```

### 目录结构
```
common/      共享底座: profile / envelope / llm / confidence / retriever / knowledge /
             embeddings / skill_matcher / skill_taxonomy / mock_data / config / profile
agents/      checklist(#4) tracker(#5) comparator(#6) navigator(#7)
data/        静态知识: 招生规则 / 状态翻译 / 竞品数据集 / 岗位-模块映射 / skill taxonomy /
             模块目录(真实 NUSMods) / 阈值 / 知识库 jsonl
admin/       管理员自然语言录入工具(CLI + Web) + 校验/归档/审计/回滚
refresh/     分级数据刷新管线(抓取→决策→自动放行/人工审核)
eval/        质量评估框架(runner/metrics)+ 阈值校准(RAG / skill match)
student/     学生端 Web(自然语言/简历 → 提取 → 确认表单 → #4+#6+#7 结果)
docs/        本总览 + 13 份分文档 + superpowers/{plans,specs}
tests/       确定性测试(不依赖 LLM)
run.py       CLI 演示;supervisor.py intent→agent 路由
```

---

## 4. 四个 Agent 现状

| # | Agent | 规则引擎(engine) | LLM 叙述(agent) | 关键特性 |
|---|-------|------------------|------------------|---------|
| 4 | Checklist | `build_checklist`:base + conditional items,按 `admissions_rules.json` 条件触发(国籍/学历/经验/学历认定);算 status/deadline/urgency | 每项材料生成 `why` 解释 | 国籍→语言证明=官方合规规则;unknown 学历走澄清不过触发 |
| 5 | Tracker | 状态机 + 状态翻译 + 截止提醒;`due_now`/`dispatch_due` 去重投递 | 把状态码翻成人话 + 下一步 | 数据走 mock 状态机;**通知引擎已落地:`configure_reminders`(渠道/频率/按里程碑静音)+ `daily_digest` 合并 + 去重投递 + 可插拔 `Notifier` 真发邮件(SMTP via config,未配则离线 record-only)** |
| 6 | Comparator | `compare`:`derive_role_strengths` 可辩护推导 + 加权评分(role_fit/cost/duration,只读 verified) | fit narrative,不排名(过 `violates_ranking` 护栏) | 数据只来自人工审核集;disclaimer 恒在;**v3 已落地(方向 D):三态 cell `verified/unknown/synthesis` + facts↔synthesis 分区 + 确定性防排名护栏(展示 11 维)** |
| 7 | Navigator | **v3 进度感知**:规则建候选池(岗位课 ∪ 按缺口纳入,排除已修)+ `select_modules` LLM 受约束挑选 + 校验 + 规则兜底;已修→技能(`module_skills.json`)缩小缺口;毕业进度不重复计 | 选课/职业建议(LLM 受约束) | 接入真实 NUSMods 目录;**永不输出不存在的模块**;区分 `recommend_courses`/`recommend_career_path`;已修代码软校验;consent + 公平性不变量;SkillMatcher 端点不可达时降级规则 |

**测试状态(最近记录)**:全套 266 passed + 1 skipped;`eval.runner` 12/12;`eval.calibrate`(embedding)best 0.92。

---

## 5. 数据资产(`data/`)

| 文件 | 用途 | 来源/可信度 |
|------|------|-----------|
| `admissions_rules.json` | #4 材料规则(base + conditional) | 人工维护(admin 高风险类) |
| `status_translations.json` | #5 状态码→人话 | 人工维护(admin 低风险类) |
| `programs_dataset.json` | #6 竞品对比(5 所真实项目) | `trusted=false`,**永远强制人工审核**,每项带 `source_url`+`fetched_at` |
| `module_catalog.json` | #7 课程目录 | **真实 NUSMods 数据**(抓取+人工批准),`trusted=true` 可自动放行 |
| `role_module_map.json` | #7 岗位→模块映射 | 人工维护,模块代码对齐真实 NUS |
| `skill_taxonomy.json` | #7 技能 taxonomy(9 技能) | ESCO/O*NET 编码引用 |
| `thresholds.json` / `match_thresholds.json` | RAG / skill 匹配阈值(按后端分节) | 由 `eval.calibrate` / `eval.skill_calibrate` 校准产出 |
| `knowledge/*.jsonl` | RAG 知识库(admissions/curriculum/faq) | curated |

---

## 6. 研究方向 A/B/C/D 状态

路线图见 [11-research-roadmap.md](11-research-roadmap.md);依赖链执行顺序 **B → A → C/D**。

| 方向 | 内容 | 状态 | 设计/计划 |
|------|------|------|----------|
| **B** | 推荐/对比质量评估框架(底座) | ✅ 已落地 | `eval/{metrics,runner}.py` + cases;12/12 |
| **A** | RAG 检索 + 阈值校准 | ✅ 已落地 | [12](12-rag-calibration-design.md) · [plan](superpowers/plans/2026-06-07-rag-calibration.md);BM25 acc 1.0 / embedding 0.92,按后端两套阈值,政策类安全转人工 |
| **C** | 个性化 taxonomy + 公平性 | ✅ 已落地(7 子任务) | [13](13-personalization-fairness-design.md) · [plan](superpowers/plans/2026-06-07-personalization-fairness.md);背景→技能 规则 f1=1.0 vs embedding 0.685;consent gate + 排除 country 不变量 |
| **D** | #6 多维对比 + fact/synthesis 分离 | ✅ 已落地 | [spec](superpowers/specs/2026-06-08-comparator-fact-synthesis-design.md) · [plan](superpowers/plans/2026-06-08-comparator-fact-synthesis.md);展示维度扩到 11(含 PDF 4 维),每格三态 `verified/unknown/synthesis`,评分只读 verified 的 3 信号,facts↔synthesis 分区 + 确定性防排名护栏;220 passed |

---

## 7. 运行方式

```bash
pip install -r requirements.txt

# CLI 演示(虚拟数据)
python run.py --list-profiles
python run.py checklist --profile 1   # #4
python run.py status    --profile 3   # #5
python run.py compare   --profile 1   # #6
python run.py courses   --profile 1   # #7

# 学生端 Web(自然语言/简历 → 提取 → #4+#6+#7)
python -m student.webapp              # http://127.0.0.1:5001

# 管理员录入 Web / refresh 管线 / 评估
python -m admin.webapp                # http://127.0.0.1:5000
python -m refresh.run module_catalog --live   # 抓真实 NUSMods
python -m eval.runner                 # 记分卡
python -m pytest tests/ -q            # 测试

# DeepSeek key(可选,启用真实叙述/提取):/settings 页填写,或 env DEEPSEEK_API_KEY/DEEPSEEK_MODEL
```

详见 [README](../README.md)(面向使用者的完整说明)。

---

## 8. 文档地图

| 文档 | 内容 |
|------|------|
| [README](../README.md) | 面向使用者:安装/运行/各功能入口 |
| [CHANGELOG](../CHANGELOG.md) | **变更历史(每次变动追加)** |
| [01 user-profile-schema](01-user-profile-schema.md) | 统一用户画像字段 |
| [02 interface-contracts](02-interface-contracts.md) | 我的 4 模块 ↔ 队友模块的契约(上游/RAG/escalation) |
| [03 technical-design](03-technical-design.md) | #4–#7 可运行 agent 整体技术设计 |
| [04 admin-authoring](04-admin-authoring-design.md) | 管理员自然语言录入工具 |
| [05 refresh-pipeline](05-refresh-pipeline-design.md) | 分级刷新管线 |
| [06 collaboration-guide](06-collaboration-guide.md) | 团队协作上手 |
| [07 checklist-v2](07-checklist-v2-design.md) | #4 深化 |
| [08 tracker-v2](08-tracker-v2-design.md) | #5 深化 |
| [09 comparator-v2](09-comparator-v2-design.md) | #6 深化(v2;v3 见 D spec) |
| [10 navigator-v2](10-navigator-v2-design.md) | #7 深化 |
| [11 research-roadmap](11-research-roadmap.md) | A/B/C/D 路线图 |
| [12 rag-calibration](12-rag-calibration-design.md) | 方向 A 设计 |
| [13 personalization-fairness](13-personalization-fairness-design.md) | 方向 C 设计 |
| [specs/](superpowers/specs/) · [plans/](superpowers/plans/) | brainstorm spec / 实现计划 |

### 维护提醒(hook)
项目配有 `.claude/settings.json` 的 PostToolUse hook:每次 `Write`/`Edit` 改到源码目录(`agents/ common/ data/ refresh/ admin/ student/ eval/`)后,会提醒「更新 CHANGELOG.md 与 docs/00-project-overview.md」。提醒为非阻塞,内容仍需人工填写。
