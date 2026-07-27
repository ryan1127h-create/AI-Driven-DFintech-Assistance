# User Profile Schema(统一用户画像)

> **状态**:W1 定稿候选 · 待团队 review
> **负责人**:[你的名字] · **消费方**:#4 Checklist / #5 Status / #6 Comparison / #7 Recommendation
> **原则**:这是 #4/#5/#6/#7 四个模块**唯一的用户数据入口**。所有模块从此 schema 取数,不得各自新增私有 profile 字段。新增字段须改本文件并通知全队。

---

## 1. 为什么需要它

| 字段来源 | 谁产生 | 谁消费 |
|---------|--------|--------|
| 身份 / lifecycle_stage | 认证模块 + 对话/意图模块 | 全部 4 块 |
| academic / work / 技能 | 用户显式输入(对话采集) | #4 #6 #7 |
| target_roles | 用户显式输入 | #6 #7 |
| application_type | 用户输入 / 招生系统 | #4 |
| application 状态 | 招生系统(MVP 用 mock) | #5 |
| consent_flags | 用户授权 | #5(reminder) #6/#7(个性化) |

> ⚠️ **#4 和 #7 共享** academic/work/技能;**#6 和 #7 共享** `target_roles`。任何一个字段改名都会同时影响多块——这就是要统一的原因。

---

## 2. Schema 定义(JSON 形态)

```jsonc
{
  // ---------- 身份与阶段 ----------
  "user_id": "u_10293",              // string, 必填, 全局唯一
  "lifecycle_stage": "applicant",    // enum, 必填(见 §3.1)
  "authenticated": true,             // bool, 必填; 未登录用户只能用 #6 公共发现

  // ---------- 学术背景 ----------
  "academic_background": {           // object, #4/#6/#7 必填; prospect 阶段可部分缺省
    "degree_level": "bachelor",      // enum: high_school|bachelor|master|phd
    "field_of_study": "computer_science", // string(受控词表见 §3.4)
    "institution": "XYZ University", // string, 可选
    "graduation_year": 2022,         // int, 可选
    "degree_classification": "second_upper" // 可选 enum: first|second_upper|second_lower|third|pass|unknown(#4 用)
  },

  // ---------- 工作与地域 ----------
  "work_years": 2,                   // number, 可选(默认 0)
  "work_domain": "banking",          // enum, 可选: banking|tech|consulting|fintech|other|none
  "country": "SG",                   // ISO 3166-1 alpha-2, 可选

  // ---------- 技能与知识 ----------
  "technical_proficiency": "intermediate", // enum: none|basic|intermediate|advanced
  "finance_knowledge": "basic",            // enum: none|basic|intermediate|advanced

  // ---------- 目标 ----------
  "target_roles": ["fintech_pm", "quant_risk"], // string[], #6/#7 用(受控词表见 §3.2)
  "preferred_learning_style": "structured",     // enum, 可选: structured|exploratory
  "application_type": "full_time",              // enum: full_time|part_time, #4 用

  // ---------- 申请状态(#5 专用, 其余块只读) ----------
  "application": {                   // object, applicant+ 阶段才有
    "application_id": "app_55021",   // string
    "status_code": "UNDER_REVIEW",   // enum(原始状态码, 见 §3.3)
    "submitted_documents": ["transcript", "cv"], // string[]
    "document_status": { "transcript": "verified", "cv": "rejected" }, // 可选 map<code, missing|submitted|under_review|verified|rejected>(#4 优先于 submitted_documents)
    "deadlines": { "application_deadline": "2026-06-03", "offer_acceptance": "2026-07-15" } // map<string, ISO-date>;#4 用 application_deadline 算紧急度
  },

  // ---------- 授权标记 ----------
  "consent_flags": {                 // object, 必填
    "personalization": true,         // 允许 #6/#7 基于画像个性化
    "reminders": true,               // 允许 #5 主动推送
    "alumni_matching": false         // (#7 职业推荐里的校友匹配, MVP 可不启用)
  }
}
```

---

## 3. 受控词表(Enums)

### 3.1 `lifecycle_stage`
`prospect` · `applicant` · `admitted` · `current` · `graduating` · `alumni`
> 与全队对话/意图模块共用同一套值,**不得各自定义**。

### 3.2 `target_roles`(MVP 先支持这 6 个, #7 映射表按此对齐)
| 值 | 中文 |
|----|------|
| `fintech_pm` | 金融科技产品经理 |
| `quant_risk` | 量化/风险 |
| `digital_banking` | 数字银行 |
| `payments` | 支付 |
| `compliance_regtech` | 合规/监管科技 |
| `data_analytics` | 数据分析 |

### 3.3 `application.status_code`(原始码 → #5 负责翻译成人话)
`DRAFT` · `SUBMITTED` · `UNDER_REVIEW` · `DOCS_REQUIRED` · `OFFER` · `WAITLIST` · `REJECTED` · `ACCEPTED`

### 3.4 `field_of_study`(受控词表节选, 可扩展)
`computer_science` · `finance` · `economics` · `engineering` · `mathematics` · `business` · `other`

---

## 4. 字段责任矩阵(谁填 / 谁读)

| 字段 | 必填 | 来源 | #4 | #5 | #6 | #7 |
|------|:---:|------|:--:|:--:|:--:|:--:|
| user_id | ✅ | 认证 | R | R | R | R |
| lifecycle_stage | ✅ | 对话/意图 | R | R | R | R |
| academic_background | ◐ | 用户输入 | R | | R | R |
| work_years / work_domain | | 用户输入 | R | | R | R |
| country | | 用户输入 | R | | R | |
| technical_proficiency | | 用户输入 | | | | R |
| finance_knowledge | | 用户输入 | | | | R |
| target_roles | ◐ | 用户输入 | | | R | R |
| application_type | ◐ | 用户/招生 | R | | | |
| application.* | ◐ | 招生系统(mock) | R(只读) | R/W | | |
| consent_flags | ✅ | 用户授权 | | R | R | R |

> R=读 · W=写 · ◐=该模块触发时必填,其它阶段可缺省

---

## 5. 缺省与校验规则

- **渐进式采集**:prospect 阶段允许只有 `lifecycle_stage` + 部分字段;模块触发时若缺必填字段,应返回"需要补充 X"的 clarification,而不是报错。
- **缺失值约定**:数值缺省 = `0` 或 `null`(团队统一选一个,建议 `null`);enum 缺省 = 字段不出现,不要塞空字符串。
- **consent 默认值**:未明确授权一律视为 `false`(隐私安全默认)。
- **不可推断**:不得从 `country`/`institution` 等推断敏感属性(对应文档 §3 "avoid discriminatory inference")。

---

## 6. 变更流程
本 schema 任何字段的增删改:① 改本文件 → ② 在团队群同步 → ③ 受影响模块确认。**禁止口头约定后直接改代码。**
