# Interface Contracts(我的 4 个模块 ↔ 队友模块)

> **状态**:W1 定稿候选 · 待团队 review
> **覆盖模块**:#4 Checklist · #5 Status/Reminders · #6 Comparison · #7 Course/Career Rec
> **目的**:把"我的 4 块"与队友的**对话/意图模块、RAG/知识模块、Escalation 模块**之间的边界定死。团队项目 80% 的返工来自这些契约没对齐——本文件就是为消除它而写。
> **配套**:所有用户数据走 [`01-user-profile-schema.md`](01-user-profile-schema.md),本文件不重复定义画像字段。

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

## 6. W1 必须落地的确认清单

- [ ] §1.2 的 7 个 intent 名 → 与对话模块负责人逐条确认拼写
- [ ] §1.3 返回信封格式 → 对话模块确认能渲染
- [ ] §2 EscalationRequest → 与 escalation 负责人确认字段 + 上报方式 + case_id 由谁生成
- [ ] §3 RAG 接口 → 与知识模块负责人确认 query/namespace/返回格式
- [ ] [`01-user-profile-schema.md`](01-user-profile-schema.md) → 全队确认 UserProfile 字段
- [ ] §4 #6 数据集字段 + 合规 disclaimer → 团队 + 导师确认口径
