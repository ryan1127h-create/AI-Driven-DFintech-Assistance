# Interface Contracts(我的 4 个模块 ↔ 队友模块)

> **状态**:W1 定稿候选 · 待团队 review
> **覆盖模块**:#4 Checklist · #5 Status/Reminders · #6 Comparison · #7 Course/Career Rec
> **目的**:把"我的 4 块"与队友的**对话/意图模块、RAG/知识模块、Escalation 模块**之间的边界定死。团队项目 80% 的返工来自这些契约没对齐——本文件就是为消除它而写。
> **配套**:所有用户数据走 [`01-user-profile-schema.md`](01-user-profile-schema.md),本文件不重复定义画像字段;与队友 `rag-data` schema 的**字段映射**见 §6。

---

## 0. 数据流总览

```

### 0.1 生命周期分流(W2 更新)

MVP 不再把所有用户塞进同一条流程。`supervisor.lifecycle_flow(profile)` 先根据
`profile.lifecycle_stage` 分流:

| Flow | Lifecycle stage | 默认调用 |
|------|-----------------|----------|
| Applicant flow | `prospect` / `applicant` / `admitted` | #4 Checklist、#5 Status(有 application 时)、#6 Comparison |
| Student flow | `current` / `graduating` | #7 Course/Career + graduation planning |
| Alumni flow | `alumni` | MVP placeholder, 后续接 alumni matching |

如果申请者误调用选课规划,或在读学生误调用申请材料清单,`supervisor.route(...)`
会返回 `status="need_clarification"`,并在 `data.allowed_intents` 中给出当前阶段可用意图。

### 0.2 官方资料相似度门控(W2 更新)

当 RAG/知识模块把检索结果传入 slots 时,我的四个模块统一先过 confidence gate:

```jsonc
{
  "user_query": "Can I apply after the deadline?",
  "rag_chunks": [
    { "text": "...", "source_id": "admissions#deadline", "score": 0.83 }
  ]
}
```

默认规则:

| Top source similarity | 行为 |
|-----------------------|------|
| `< 0.60` | 转人工, reason=`low_confidence` |
| `0.60 - 0.72` | 追问澄清, `status="need_clarification"` |
| `>= 0.72` | 可回答 |
| 官方政策/例外/申诉类问题 `< 0.80` | 转人工, reason=`policy_ambiguity` |

本地 MVP 若没有 RAG 分数,`common/confidence.py` 会使用轻量 lexical similarity 兜底;
真实系统应优先使用 RAG 团队提供的 embedding similarity score。
                 ┌─────────────────────┐
  用户输入  ───▶  │ 对话 / 意图模块(队友) │  产出 {intent, slots, profile_ref}
                 └──────────┬──────────┘
                            │ ① 上游调用契约(§1)
                            ▼
        ┌───────────────────────────────────────┐
        │   我的 4 个 Agent                       │
        │   #4 Checklist · #5 Status · #6 Cmp · #7 Rec │
        └───┬───────────────────────────┬────────┘
            │ ② RAG 调用(§3)            │ ③ Escalation 上报(§2)
            ▼                            ▼
   ┌─────────────────┐         ┌──────────────────────┐
   │ RAG/知识模块(队友)│         │ Escalation 模块(队友) │
   └─────────────────┘         └──────────────────────┘
```

---

## 1. ① 上游契约:对话/意图模块 → 我的 Agent

### 1.1 入站请求格式(队友给我)
```jsonc
{
  "intent": "generate_application_checklist", // 见 §1.2 意图清单
  "user_id": "u_10293",
  "profile": { /* UserProfile 对象, 见 schema 文档 */ },
  "slots": {                  // 意图槽位, 由对话模块抽取; 每个意图需要的槽见 §1.3
    "target_role": "fintech_pm"
  },
  "session_id": "s_abc",      // 多轮上下文 id
  "locale": "en"              // 语言(MVP 默认 en)
}
```

### 1.2 意图清单(队友按此识别并路由到我)
| Intent 名 | 路由到 | 说明 |
|-----------|--------|------|
| `generate_application_checklist` | #4 | 生成个性化材料清单 |
| `check_missing_documents` | #4 | 检查缺什么 |
| `get_application_status` | #5 | 查申请状态 |
| `configure_reminders` | #5 | 设置/修改提醒偏好 |
| `compare_programs` | #6 | 与其它项目对比 |
| `recommend_courses` | #7 | 推荐模块 |
| `recommend_career_path` | #7 | 职业路径 + 技能差距 |

> 🔴 **W1 必须和对话模块负责人逐条确认这 7 个 intent 名的拼写**——一个字母不一致就路由失败。

### 1.3 各意图的统一返回格式(我给对话模块)
所有 Agent 统一返回这个信封,便于对话模块渲染:
```jsonc
{
  "status": "ok",            // ok | need_clarification | escalated | error
  "answer_type": "official", // official | advisory | recommendation(对应文档"答案分级")
  "speakable": "你目前还缺：成绩单、推荐信。", // 给用户看的自然语言
  "data": { /* 结构化结果, 各意图不同, 见 §4 */ },
  "sources": ["admissions_req_v3#p2"], // 可选, 来源引用
  "missing_fields": ["academic_background.field_of_study"], // status=need_clarification 时填
  "escalation": null         // status=escalated 时填 EscalationRequest(见 §2)
}
```

---

## 2. ③ 下游契约:我的 Agent → Escalation 模块

当 #4/#5 遇到规则覆盖不了的情况(特殊学历认定、例外、低置信),统一上报这个 payload:

```jsonc
// EscalationRequest
{
  "case_id": "esc_77a3",          // 我生成, uuid
  "source_agent": "checklist",    // checklist | status | comparison | recommendation
  "reason": "exception_case",     // 见 §2.1
  "confidence": 0.32,             // 0~1, 触发阈值默认 < 0.5
  "user_id": "u_10293",
  "lifecycle_stage": "applicant",
  "conversation_summary": "申请人持境外三年制本科, 规则表无对应学历认定条目。",
  "structured_context": {         // 机器可读上下文, 便于人工快速判断
    "profile_snapshot": { /* 关键字段 */ },
    "rule_hit": null,
    "user_question": "我的三年制学位符合要求吗?"
  },
  "suggested_routing": "admissions_office" // 我建议的目标团队(可选)
}
```

### 2.1 `reason` 枚举(对齐文档第 11 节)
`low_confidence` · `policy_ambiguity` · `exception_case` · `emotionally_sensitive` · `complaint_appeal`

> 🔴 **W1 和 escalation 模块负责人确认**:① payload 字段名;② 上报方式(函数调用 / 队列 / API);③ 谁生成 `case_id`(建议我方生成,避免来回)。

---

## 3. ② 旁路契约:RAG / 知识模块

#4(解释招生条款)和 #6(对比叙述)需要调队友的知识检索。统一走一个接口,**不要各建 retriever**:

```jsonc
// 请求
{ "query": "MSc DFT 推荐信要求", "namespace": "admissions", "top_k": 3 }
// 命名空间: admissions | curriculum | faq | policy

// 返回
{
  "chunks": [
    { "text": "...", "source_id": "admissions_req_v3#p2", "score": 0.88 }
  ]
}
```
约定:**我只消费 `chunks` 并把 `source_id` 透传到 §1.3 的 `sources`**;不在我侧做向量库。RAG 模块保证返回的内容来自 curated 源。

---

## 4. 各模块的 `data` 结构(给对话模块渲染用)

### #4 `generate_application_checklist` → data
```jsonc
{
  "items": [
    { "key": "transcript", "label": "成绩单", "required": true,
      "status": "missing", "why": "用于核验学术背景" },
    { "key": "cv", "label": "简历", "required": true, "status": "submitted" }
  ],
  "missing_count": 1
}
```

### #5 `get_application_status` → data
```jsonc
{
  "status_code": "UNDER_REVIEW",
  "human_status": "材料齐全, 正在审核中",      // #5 的状态翻译层产出
  "next_step": "无需操作, 预计 2 周内有结果",
  "deadlines": [ { "name": "offer_acceptance", "date": "2026-07-15" } ],
  // v3 通知引擎新增:
  "due_now": [ { "kind": "single|digest", "channels": ["in_app","email"],
                 "subject": "...", "message": "...", "urgency": "info|soon|urgent",
                 "reminder_keys": ["offer_acceptance:2026-07-15"] } ],  // 预览,只读不发
  "notification_prefs": { "channels": ["in_app","email"], "frequency": "immediate|daily_digest|off",
                          "muted_milestones": [] }
}
```
> #5 数据来源 MVP 用 **mock 状态机**(见 §5),非真实招生 API。`due_now` 只是「现在应投递的预览」——读状态**不**触发发送;真正发送由 `dispatch_due` 经可插拔 `Notifier`(配 SMTP 才真发,否则 record-only)完成。

### #5 `configure_reminders` → data
```jsonc
// 入站 slots: {"channels":["in_app","email"], "frequency":"daily_digest",
//             "mute":["application_deadline"], "unmute":["offer_acceptance"]}
{
  "notification_prefs": { "channels": ["email"], "frequency": "daily_digest",
                          "muted_milestones": ["application_deadline"] }
}
```
> 非法值(渠道/频率/里程碑名)→ `status="need_clarification"`,`missing_fields` 标出问题项。变更写回 `profile.notification_prefs`(状态携在 profile 上);sent-state 存 `profile.notification_log`(按 reminder key 去重,digest 记子 key → 跨频率只发一次)。

### #6 `compare_programs` → data(v3:fact/synthesis 分区)
```jsonc
{
  "dimensions": ["curriculum_focus","duration","format","fees","intake","scholarship","gmat_gre",
                 "typical_profile","industry_orientation","technical_depth","career_pathways"],
  "facts_table": {                       // 全部展示维度,每格带 kind(verified/unknown 带来源;synthesis 不带)
    "rows": [
      { "program": "NUS ...", "is_target": true,
        "facts": {
          "fees": {"text":"S$74,120 ...","kind":"verified","source_url":"...","fetched_at":"2026-06-05"},
          "technical_depth": {"text":"...","kind":"synthesis","source_url":null,"fetched_at":null}
        } }
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
> 🔒 **合规硬约束**:`facts_table` 含全部展示维度,**每格带 `kind`**(verified/unknown 带来源,synthesis 为系统归纳、不带来源),数据只来自**人工审核数据集**;`synthesis` 区为非官方综合(分数/best_for_you/narrative),opt-out 时整块为 `null`;`narrative` 经确定性防排名护栏,不得生成排名或"X 优于 Y";评分只用 verified 的 3 信号(role_fit/cost/duration),主观维度不打分。

### #7 `recommend_courses`(handle)/ `recommend_career_path`(career)→ data(v3:进度感知 + LLM 受约束选课)

两个意图路由到**不同** handler。

`recommend_courses`(选课视角):
```jsonc
{
  "target_role": "fintech_pm",
  "recommended": [   // 选中的「待修」模块(已排除已修)
    { "code": "FT5002", "name": "...", "credits": 4, "skills": ["ai_ml","finance"],
      "closes_gaps": ["data_analytics"], "prereq_ok": true, "verified": true, "source": "gap" }
  ],
  "already_completed": [ { "code": "BMS5312", "name": "..." } ],  // 已修且属推荐(✓)
  "unrecognized_completed": ["ZZZ000"],   // 已修代码软校验:课程库找不到,提示核对(E)
  "selection_source": "llm",              // "llm"=AI在候选内挑选 | "rule"=确定性兜底
  "skill_gaps": ["产品/业务理解"],
  "graduation_progress": { "required":52, "completed_credits":12, "planned_credits":16, "remaining":24 },
  "study_plans": { "full_time": {...}, "part_time": {...} },     // 只排待修模块
  "prereq_warnings": [ { "code":"...", "missing":["..."] } ],
  "explanation": "...", "personalized": true
}
```
`recommend_career_path`(职业视角):
```jsonc
{
  "target_role": "fintech_pm",
  "required_skills": ["product","finance","data_analytics","programming"],
  "matched_skills": ["finance","programming"],   // 含已修课程贡献的技能(D)
  "skills_from_courses": ["finance"],
  "skill_gaps": ["产品/业务理解"],
  "gap_closing_modules": [ { "code":"...", "closes_gaps":["product"], ... } ],  // 不含排课
  "selection_source": "llm", "unrecognized_completed": [], "explanation": "...", "personalized": true
}
```
> 🔒 **推荐内核**:规则建候选池(岗位课 ∪ 按缺口纳入的真课,**排除已修**)→ LLM **只在候选内**挑选/排序 → 校验(编造的 code 丢弃)→ 无 key/离线/全无效走**确定性规则兜底**(`selection_source`);**永不输出不存在的模块**。已修课程经 `module_skills` 反推技能缩小缺口(D);毕业进度不重复计已修(B)。

---

## 5. Mock 契约(#5 状态机, MVP 用)

真实招生/CRM 接口不可得,#5 用本地状态机模拟。**接口形状与真实 API 对齐**,后期可无痛替换:
```
DRAFT → SUBMITTED → UNDER_REVIEW → {OFFER | DOCS_REQUIRED | WAITLIST | REJECTED}
OFFER → ACCEPTED
```
- mock 提供 `get_status(application_id)` 返回 `{status_code, deadlines, submitted_documents}`。
- 报告中明确标注:**真实系统对接 = future work / 已知风险**。

---

## 6. 用户画像统一(已实施)

> **状态**:agent-backend 侧**已落地并有测试**;`rag-data/` 侧**零改动**(队友 pipeline,只读)。
> 提议与取舍理由见 [`14-profile-unification.md`](14-profile-unification.md);**契约以本节为准**,两处不一致时本节优先(14 号文有 3 处已过期,见 §6.8)。
> 代码入口:`common/profile.py`(权威模型)· `common/profile_adapter.py`(双向适配器)· `tests/test_profile_adapter.py`(69 tests,两个真实 fixture 从磁盘读入并 key-for-key 往返)。

### 6.0 四份定义的归属

| # | 位置 | 统一后 |
|---|---|---|
| 1 | `common/profile.py` `UserProfile` | **唯一权威定义**。新增 11 个字段,全部 optional + 安全默认(§6.2),原有调用方无需改动 |
| 2 | `app/api/chat.py` `UserProfile`(2 字段) | 改名 **`ChatUserProfile`**,降级为传输 DTO。`stage` 改用权威 `LifecycleStage` 类型,别名映射走 `resolve_wire_stage()`;`name` **不并入**画像(公开仓库,姓名属可直接识别个人信息) |
| 3 | `student/api2.py` `RecommendationProfile`(9 个裸 `str`) | 改名 **`RecommendationProfileInput`**,每个字段都用权威词表类型。未知值 → 422 并回显原值,不再静默变 `current` |
| 4 | `rag-data/docs/user_profile_schema.md` + `scripts/profile_extract.py` | **不改**。用 `common/profile_adapter.py` 显式双向对接:`from_rag_data(src, *, user_id, degree_level=None)` / `to_rag_data(profile)` |
| — | `student/api.py`(旧重复实现,含 `_enum_value`) | 已删除,无 importer 残留 |

`ChatUserProfile` / `RecommendationProfileInput` 是**传输 DTO,不是第二份画像定义**:它们只承载各自前端实际发送的字段,并立刻转成权威 `UserProfile`。命名刻意区分——两个都叫 `UserProfile` 的类正是当初漂移的起点。

### 6.1 双方都有的字段

| rag-data 字段(类型) | 权威字段(类型) | 转换 | 备注 |
|---|---|---|---|
| `user_id`(string) | `user_id: str` | identity | `from_rag_data` 要求显式传入存储 key;blob 里若也带 `user_id` 且两者不等 → **报错**,不选边(否则等于用别人的 key 载入某人画像) |
| `lifecycle_stage`(enum,5 值) | `lifecycle_stage: LifecycleStage`(enum,6 值) | **renamed 词表** | 入:`enrolled`/`student` → `current`;出:`current` → `enrolled`,`graduating` → `null`。见 §6.4 |
| `academic_background.std`(text→std) | `academic_background.field_of_study: FieldOfStudy` | renamed(严格) | 映射不到的关键词(如 `accounting`)→ **报错**,不降级成 `other` |
| `academic_background.raw`(text) | `raw_inputs["academic_background"]: str` | renamed(原样保存) | ⚠️ 与 14 号文 §四末段说法不同:实现的是**单个 `raw_inputs` dict**(key = 承接它的权威字段名),不是每字段一个 `*_raw` 列 |
| —(你侧无此概念) | `academic_background.degree_level: DegreeLevel`(**必填**) | 调用方提供 | 有 `std` 但未传 `degree_level=` → **报错**。不默认 `bachelor`——那等于替用户编造一个他没声明的学历 |
| `tech_level.std`(3 级) | `technical_proficiency: Proficiency`(4 级) | 入 renamed / 出 **LOSSY** | 入:`strong` → `advanced`;出:`intermediate` + `advanced` → `strong`。见 §6.6 |
| `tech_level.raw`(text) | `raw_inputs["technical_proficiency"]` | renamed(原样保存) | |
| `work_years`(number) | `work_years: int \| None` | identity | |
| `target_role_std`(6 个 role_id) | `target_roles: list[TargetRole]` | 结构转换 / 出 **LOSSY** | **值域完全一致**(6 个 `role_id` 逐字相同,零对齐成本)。入:单值 → 0/1 元素列表;出:只发 `target_roles[0]` |
| `target_role_raw`(text) | `raw_inputs["target_roles"]` | renamed(原样保存) | 出向原样回写。**绝不**把被丢弃的 role id 塞进这里——它是用户原话,你的设置页会回显给用户 |
| `personalization_opt_out`(bool) | `consent_flags.personalization: bool` | **NEGATED** | 极性与默认值一起反转。见 §6.5 |

### 6.2 只有 rag-data 有 → 已并入权威模型

11 个新字段,**全部 optional + 安全默认**,所以此前写好的调用方一行都不用改。

| rag-data 字段(类型) | 权威字段(类型,默认) | 转换 |
|---|---|---|
| `intake_year`(enum `"2025"`/`"2026"`/`"2027"`) | `intake_year: int \| None`(`None`,1000–9999) | 类型转换 str ↔ int。用 `int` 而非枚举:新一届不用改代码。范围只由 `UserProfile` 校验(pydantic 报错同样带字段和值),适配器不复制一份边界 |
| `application_term`(text) | `application_term: str \| None`(`None`) | identity |
| `gmat` / `gre` / `toefl`(number) | `gmat` / `gre` / `toefl: int \| None`(`None`,ge=0) | identity。原样存不换算,与你 §一.4 一致;`ge=0` 是唯一约束(GMAT Focus 与旧制分段会变,写死一个区间等于编造) |
| `ielts`(number) | `ielts: float \| None`(`None`,ge=0) | identity,**必须 float**:`int` 会把 6.5 截成 6(依据你 `profile_extract.as_half()`) |
| `asked_topics`(system) | `asked_topics: list[str]`(`[]`) | identity;键缺席与 `null` 同视为 `[]`(这是 null→empty 恒等,不是对不可映射值的兜底) |
| `updated_at`(system) | `updated_at: str \| None`(`None`) | identity,ISO 8601 字符串(与本文件 `StatusEvent.date` / `deadlines` 同一约定) |
| `school_tier`(text) | `school_tier: str \| None`(`None`) | identity,纯记录 |
| `target_industry.std`(text→std) | `target_industry: str \| None`(`None`) | identity。仍是自由文本:你 §六 把它推到第二版,尚无受控词表,先不强加 |
| `target_industry.raw`(text) | `raw_inputs["target_industry"]` | renamed(原样保存) |
| —(承接你的 `{raw, std}` 结构) | `raw_inputs: dict[str, str]`(`{}`) | `to_rag_data` 用它重建你的嵌套 pair。**仅供回显,永不进检索/匹配** |

### 6.3 只有权威模型有 → 你侧无需填

`authenticated` · `email` · `country` · `work_domain` · `finance_knowledge` · `preferred_learning_style` · `application_type` · `completed_modules` · `application`(含 `status_code` / `document_status` / `deadlines` / `status_history`)· `consent_flags.reminders` · `consent_flags.alumni_matching` · `notification_prefs` · `notification_log` · `academic_background` 的 `institution` / `graduation_year` / `degree_classification`。

这些服务 MVP#4–#7。`to_rag_data` **不发**它们(你侧没有槽位也没有消费方),`from_rag_data` 也不会碰它们。

### 6.4 ⚠️ `lifecycle_stage`:6 值词表

```
prospect     # 想了解一下
applicant    # 申请中
admitted     # 已录取、未入学
current      # 在读        ← 你的 enrolled、chat 前端的 student 都映射到这里
graduating   # 即将毕业    ← MVP#5 的毕业提醒需要挂载点;你侧无对应词
alumni       # 校友
```

| 权威值 | 入向接受的写法 | 出向发给你侧 |
|---|---|---|
| `prospect` / `applicant` / `admitted` / `alumni` | 同名 | 同名 |
| `current` | **`enrolled`**(你的抽取器)、**`student`**(chat 前端) | `enrolled` |
| `graduating` | (你侧无此值) | **`null`**,不是 `enrolled`。见 §6.6 |

三条硬约定:

1. **别名只住在适配器的一张表里**(`RAG_STAGE_TO_AUTHORITY`),`LifecycleStage` 永远只有 6 个成员。
2. **入向不接受我方词** `current` / `graduating`,也**不做大小写折叠**。你的 `_sanitize` 已经只输出小写受控值,所以收到 `Applicant` 说明存储层漂移了,该被看见而不是被抹平。
3. **`lifecycle_stage` 缺失(`null`)也报错**。用户没说时你的抽取器留 `null` 是对的,但那时正确动作是**去问**,不是替他假设一个阶段。

### 6.5 ⚠️⚠️ `personalization`:opt-in、默认关,适配器取反

| | rag-data | 权威模型 |
|---|---|---|
| 字段 | `personalization_opt_out` | `consent_flags.personalization` |
| 极性 | opt-**out**(`true` = 退出) | opt-**in**(`true` = 同意) |
| 默认 | 键缺席 / `false` → **做**个性化 | `False` → **不做**个性化 |

**两者极性相反,默认行为也相反**,所以适配器取反,并且**「未记录」不等于「同意」**:

| 你侧 `personalization_opt_out` | 我方 `consent_flags.personalization` |
|---|---|
| 键缺席 | `False`(不个性化) |
| `null` | `False` |
| `false`(用户看过开关、没有退出) | `True` |
| `true` | `False` |
| 非 bool(`"true"` / `1` / `[]`) | **报错** |

出向:`personalization_opt_out = not consent_flags.personalization`。

> ⚠️ **这条改变了你那侧的默认行为:从「默认个性化」变成「默认不个性化」。** 只有用户明确记录过 `false` 才开。依据是 PDF §3 的退出个性化要求与 [`01-user-profile-schema.md`](01-user-profile-schema.md) §5 的 privacy-safe default。把「未表态」翻译成「同意」,等于替你库里所有从未表态的用户静默打开个性化——这是隐私默认值回归,不是命名分歧。
> 反向副作用(LOW,见 §6.8):`to_rag_data` 会把「未表态」写成 `personalization_opt_out: true`,即「已明确退出」。如果你的设置页把它当用户决定回显,会显示一个用户从未做过的选择。

### 6.6 有损方向:不要当成可往返

| 方向 | 字段 | 损失 | 为什么这样选 |
|---|---|---|---|
| 权威 → rag-data | `technical_proficiency` | **LOSSY**:`intermediate` 与 `advanced` 都变 `strong` | 你的量表只有 3 级。读回来时 `strong` → `advanced`,所以 `intermediate` 的用户会被**升级**成 advanced。权威 → rag → 权威 对这个字段**不是恒等** |
| 权威 → rag-data | `target_roles` | **LOSSY**:只发第一个,其余丢弃 | 你的 `target_role_std` 是单槽位。index 0 是权威侧约定的主职业(显式 override 会插到队首,见 `student/api2.py:_ordered_target_roles`) |
| 权威 → rag-data | `lifecycle_stage = graduating` | 发 `null`(你侧的「未说明」) | 你的 5 值词表没有这个词。发 `enrolled` 能干净往返但**是谎**:它会告诉检索侧一个即将毕业的学生正在课程中期,产出自信但错误的选课建议。代价是推到你库里的 graduating 画像读回来会因「缺 stage」报错——损失在回程**响**地出现,而不是悄悄变成另一个阶段 |

入向的 `strong → advanced` 与单值 → 单元素列表都是无损的;有损只发生在出向。

### 6.7 边界失败即报错,不静默回退

`common/profile_adapter.py` 里**没有** `or default`、**没有** `except: pass`、**没有** `.get(k, 某个看起来合理的值)`。两个方向的查表都走同一个 `_mapped()`,失败抛:

```python
class ProfileMappingError(ValueError):
    field: str     # 出问题的字段名,如 "tech_level.std"
    value: object  # 收到的原值,不改写不截断
    reason: str    # 原因;查表失败时附上完整可接受集合

# str(e) == "tech_level.std='expert': no mapping defined; accepted: none, basic, strong"
```

继承 `ValueError`,所以 pydantic validator 能直接把它变成 422,现有 `except ValueError` 的调用方照旧工作;`field` / `value` 是属性而非只在文案里,调用方可以分支处理。

会报错(而非兜底)的完整清单:`lifecycle_stage` 未知或缺失 · `tech_level.std` / `academic_background.std` / `target_role_std` 未知 · 有 `academic_background.std` 但未传 `degree_level=` · `personalization_opt_out` 非 bool · `{raw, std}` 不是对象 · `intake_year` 不是四位数字(**范围**越界由 `UserProfile` 抛 pydantic `ValidationError`,同样带字段和值)· blob 里的 `user_id` 与读取用的 key 不一致 · 不可哈希的值出现在该放词的位置(`[]` 与未知词同样处理,不会变成 `TypeError`)。

被删掉的反例(旧 `student/api2.py:114`):

```python
stage = _enum_value(LifecycleStage, incoming.lifecycle_stage) or LifecycleStage.current
```

`_enum_value` 及其全部调用点已从代码库移除。

### 6.8 仍未解决(不要当成已完成)

画像定义本身已收敛,但以下问题**经验证阶段实测确认仍在**,其中两条会影响你我的联调:

| 严重度 | 位置 | 问题 |
|---|---|---|
| **HIGH** | `app/api/chat.py:38` | `resolve_wire_stage` 用 `value in _WIRE_STAGE_ALIASES`(dict 成员判断),不可哈希的 `stage`(如 `[]` / `{}`)抛 `TypeError`。pydantic `mode="before"` 只把 `ValueError`/`AssertionError` 转成 `ValidationError`,所以它逃出请求解析、变成 **HTTP 500 无诊断信息**(`stage='alumnus'` 则正确返回 422)。修法一行:一并 catch `TypeError`,或先 `isinstance(value, str)`。适配器 `_mapped()` 已经这样做了 |
| **HIGH** | `student/api2.py:65` | `personalization: bool = True`。这是唯一活跃的 HTTP 推荐边界,调用方省略该键就会拿到个性化输出,与 §6.5 的决定相反(已实测:省略键 → `skillGaps` 有值;`personalization=false` → `[]`)。翻成 `False` 不破坏任何现有测试 |
| MEDIUM | `student/profile_form.py:209` + `student/api2.py:347,380` + `student/webapp.py:59,77` | `normalize_stage` 把 `prospect`/`admitted`/`graduating`/`alumni`/`enrolled`/空/乱码**全部塌成 `applicant`**,且随后无条件覆盖抽取结果。所以 §6.4 的 6 值词表目前**在 `/extract-profile` 与 `/advise` 这两条 Flask 路径上还走不通**——`student/extract_profile.py` 的白名单已放宽到 6 值,但用户看不到效果。修 `normalize_stage` 是让它生效的前提 |
| MEDIUM | `app/api/chat.py` | **零自动化覆盖**:`langchain_core` / `langgraph` / `langchain-openai` 在 requirements.txt 里但未安装,`import app.api.chat` 直接 `ModuleNotFoundError`,`tests/` 里也没有任何引用。上面那条 500 就是「无覆盖边界会静默回归」的直接证据 |
| LOW | `common/profile_adapter.py` `to_rag_data` | 把「未表态」写成 `personalization_opt_out: true`(§6.5 末)。方向是隐私安全的,但不是 no-op |
| LOW | `student/profile_form.py:410` | Flask 表单路径对每个用户硬编码 `ConsentFlags(personalization=True, reminders=True)`,完全没有同意控制 |
| LOW | `student/api2.py:100` `_ordered_target_roles` | 两个分支(override 插队首、保序去重)**都没有测试守住**:改坏任一个,447 个测试全绿。根因是 `pick_primary_role` 会先吃 `slots['target_role']`,`profile.target_roles` 的顺序其实不参与排序。要么这个 helper 是死代码该删,要么排序本该受它影响而目前没有 |
| LOW | [`14-profile-unification.md`](14-profile-unification.md) | 3 处已过期:§一 表格仍写 `RecommendationProfile`(9 个裸 str)· §七 与 §一 仍引用已删除的 `_enum_value` 代码 · §四末段向你承诺「新增可选 `*_raw` 字段」,实际实现的是单个 `raw_inputs` dict(见 §6.1)。**最后一条最要紧,因为它是已经发给你的说法** |

仍需你侧回答(14 号文 §八 的 5 问中,1 / 3 / 4 已由 owner 单方拍定并落地,§6.4/§6.5/§6.6 即其结果):

- **`graduating`** —— 你的抽取能否支持这个新状态?若不能,出向的 `null` 就是长期方案(§6.6),`graduating` 画像无法在你库里往返。
- **`name`** —— 同意不并入画像吗?(公开仓库 + 姓名属可直接识别个人信息)

---

## 7. W1 必须落地的确认清单

- [ ] §1.2 的 7 个 intent 名 → 与对话模块负责人逐条确认拼写
      · **仍需**:本次统一不涉及 intent 命名,7 个字符串仍未和对话模块负责人逐条核对。
- [ ] §1.3 返回信封格式 → 对话模块确认能渲染
      · **仍需**:信封形状未改动,也未拿到对话模块「能渲染」的确认。
- [ ] §2 EscalationRequest → 与 escalation 负责人确认字段 + 上报方式 + case_id 由谁生成
      · **仍需**:三项全未确认。
- [ ] §3 RAG 接口 → 与知识模块负责人确认 query/namespace/返回格式
      · **仍需**:本次只对齐**画像字段**,retriever 的 `query`/`namespace`/返回形状仍未确认。
- [x] [`01-user-profile-schema.md`](01-user-profile-schema.md) 的字段集 → **本侧已定稿**
      · `agent-backend` 内的三份定义已合并为唯一权威 `UserProfile`(§6.0);新增 11 个字段全部 optional + 安全默认(§6.2);与 rag-data 的映射由 `common/profile_adapter.py` 用代码固定(§6.1、§6.4–§6.7);测试 447 passed(唯一失败是 `tests/test_embeddings.py` 的既有 RAG 缺陷,与画像无关)。
- [ ] 同一项的**跨团队确认** → 仍需 RAG 侧回 §6.8 末尾的 2 问(`graduating` 抽取支持、`name` 不并入)
      · 说明:14 号文 §八 的问题 1/3/4(`current` vs `enrolled`、技术水平级数、个性化默认值反转)已由 owner 拍定并落地,适配器让你侧零改动;剩下 2 问仍真正开放。另外 §6.8 的两条 HIGH 属**本侧未完工**,不应算在你侧头上。
- [ ] §4 #6 数据集字段 + 合规 disclaimer → 团队 + 导师确认口径
      · **仍需**:未动。
