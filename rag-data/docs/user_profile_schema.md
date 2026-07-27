# 用户画像字段规范（User Profile Schema）

> 长期记忆 / 「公开画像」功能的**接口契约**。
> 目的：用户在一次对话里说过的背景信息，沉淀成一份跨会话的画像；新开对话时系统直接读取，不必重复询问，并用于个性化检索与回答。

## 分工

| 谁 | 负责 |
|---|---|
| **画像内容**（本文档） | 字段定义、从对话中抽取、映射到检索标准词、对齐检索做个性化 |
| **画像存储**（队友） | Redis 缓存 + 长短期记忆模块、按 `user_id` 读写、设置页展示与修改接口 |

本文档是两边的约定：队友照此建存储结构，抽取侧照此产出 JSON，检索侧照此消费。

---

## 一、设计原则

1. **能驱动回答才记。** 每个字段都要能改变系统给用户的回答；纯粹「多知道一点」但用不上的信息不记（既是负担也是隐私风险）。
2. **自由填 + 后台映射。** 用户填写/修改时用自由文本（体验自然、随时可改）；凡要拿去检索的字段，系统再用 LLM 把自由文本映射成一个**标准词**，存两份：`_raw`（给用户看/改）+ `_std`（给检索用）。数字类字段不需要映射。
3. **画像随阶段变。** 同一字段对不同阶段含义不同（见「时间线」）。因此 `lifecycle_stage` 是画像的地基，先判断阶段，再决定其它字段怎么填、怎么用。
4. **抽取保守。** 拿不准的字段留空（`null`），绝不猜测。数字（GMAT/GRE/语言分）必须原样，不换算。
5. **隐私可控（PDF §3）。** 用户能看到系统记了什么、能修改、能删除、能整体退出个性化。不记姓名/邮箱/电话/性别/年龄等对回答无用但敏感的信息。

---

## 二、字段定义

图例：类型 `text` 自由文本 / `text→std` 自由文本且需映射标准词 / `number` 数字 / `enum` 枚举 / `system` 系统维护。

### 基础背景

| 字段 | 类型 | 用户可改 | 对齐的检索数据 | 说明 |
|---|---|---|---|---|
| `academic_background` 学术背景（专业） | text→std | ✅ | courses 先修判断 | 如「金融」「计算机」；映射用于判断课程是否太基础/太硬核 |
| `school_tier` 本科院校层次 | text | ✅ | —（纯记录） | 如「双非」「985」；目前只记录，不参与检索 |
| `tech_level` 技术基础 | text→std | ✅ | courses 难度 | 会不会编程/数学基础；用于选课时避开硬核课。建议标准值：`none` / `basic` / `strong` |
| `work_years` 工作年限 | number | ✅ | —（纯记录） | 整数年 |

### 考试成绩

| 字段 | 类型 | 用户可改 | 对齐的检索数据 | 说明 |
|---|---|---|---|---|
| `gmat` | number | ✅ | 招生要求 | 原样存，不换算 |
| `gre` | number | ✅ | 招生要求 | 同上 |
| `toefl` / `ielts` 语言成绩 | number | ✅ | 招生要求、语言门槛 | 分开存，只填其一即可 |

### 目标方向

| 字段 | 类型 | 用户可改 | 对齐的检索数据 | 说明 |
|---|---|---|---|---|
| `target_role_raw` 目标职业方向（原文） | text | ✅ | — | 用户原话，如「我想去大厂搞数据」 |
| `target_role_std` 目标职业方向（标准） | text→std | 系统 | **career_roles** | 映射到标准词表（见 §三）；检索选课/职业问题时带上 |
| `target_industry` 感兴趣行业 | text→std | ✅ | —（暂纯记录） | 银行/支付/加密…；和职业方向互补（做什么 vs 在哪做）。第一版可选 |

### 阶段与时间线 ⭐

| 字段 | 类型 | 用户可改 | 对齐的检索数据 | 说明 |
|---|---|---|---|---|
| `lifecycle_stage` 所处阶段 | enum | ✅ 用户自己选 | 决定时间线字段 | `prospect`（想了解一下）/ `applicant`（申请中）/ `admitted`（已录取、未入学）/ `enrolled`（在读）/ `alumni`（校友）。**优先用户手选**；若用户在对话里明说了身份，抽取时也会填。不从"问了什么话题"去猜。⚠️ `admitted`（拿 offer 未入学）与 `enrolled`（已在读）是两个不同阶段，别混 |
| `application_term` 申请目标学期 | text | ✅ | 截止日、申请材料 | **仅当阶段=prospect/applicant 时填**，如「2026 Fall」 |
| `intake_year` 入学届别 | enum | ✅ | ✅ **course_rules.intake** | **仅当阶段=admitted/enrolled 时填**，如 `2025`/`2026`/`2027`。用于精准命中对应届别的培养方案规则 |

> **时间线随阶段切换**：未录取的人有「申请时间线」，录取后变成「哪一届」。先看 `lifecycle_stage`，再决定填 `application_term` 还是 `intake_year`，另一个留空。
> `intake_year` 直接对上 `course_rules` 表的 `intake` 字段（该表已按届别区分：2025 届 6 条 / 2026 届 7 条），画像里存了届别，检索培养方案时就不会把别的届的规则讲错。

### 系统维护（用户不可改）

| 字段 | 类型 | 说明 |
|---|---|---|
| `asked_topics` 问过的话题 | system | 记录用户问过什么（学费/选课…），供避免重复、做分析。对应 intent label |
| `updated_at` 更新时间 | system | 最后更新时间戳 |
| `personalization_opt_out` 退出个性化 | system | 用户可整体关闭个性化（PDF §3 要求） |

---

## 三、目标方向的标准词表

**已定：直接用现有 6 个 career_roles**（零对齐成本，映射目标就是库里已有角色；覆盖不到再扩）。

`target_role_std` 只能取以下 6 个 `role_id` 之一，取不准则留 `null`：

| role_id | role_title | 常见用户说法（映射来源示例） |
|---|---|---|
| `quant_risk` | Quantitative / Risk Analyst | 量化、量化风险、quant、风控建模 |
| `data_analytics` | Financial Data Science / AI | 数据分析、数据科学、AI、机器学习 |
| `fintech_pm` | FinTech Product Manager | 产品经理、PM、产品 |
| `payments` | Payments / Blockchain / Digital Assets | 支付、区块链、加密、数字资产、crypto |
| `digital_banking` | Digital Banking | 数字银行、互联网银行、digital banking |
| `compliance_regtech` | Compliance / RegTech | 合规、监管科技、RegTech、风控合规 |

---

## 四、示例：一份完整画像

```json
{
  "user_id": "u_12345",
  "academic_background": { "raw": "金融本科", "std": "finance" },
  "school_tier": "双非",
  "tech_level": { "raw": "会一点 Python", "std": "basic" },
  "work_years": 2,
  "gmat": 680,
  "gre": null,
  "toefl": 100,
  "ielts": null,
  "target_role_raw": "想做量化风险那种",
  "target_role_std": "quant_risk",
  "target_industry": { "raw": "投行", "std": "banking" },
  "lifecycle_stage": "applicant",
  "application_term": "2026 Fall",
  "intake_year": null,
  "asked_topics": ["tuition", "course_planning"],
  "updated_at": "2026-07-22T14:30:00Z",
  "personalization_opt_out": false
}
```

（此人是申请中的学生，故填 `application_term`、`intake_year` 留空。录取后阶段变 `admitted`，届别填 `2026`，`application_term` 可清空。）

---

## 五、抽取与消费流程

```
用户对话
   ↓  ① 抽取（本侧，LLM，temperature=0）
结构化画像（含 _raw + _std）
   ↓  ② 存储（队友，Redis，按 user_id）
   ↓  ③ 用户在设置页查看/修改 _raw（队友界面）→ 改动后重新映射 _std（本侧）
   ↓  ④ 新开对话读回画像
   ↓  ⑤ 对齐检索（本侧）：把 _std 拼进查询，命中 career_roles / course_rules 等
个性化回答
```

---

## 六、第一版范围（已定）

**精简 7 个核心字段先上**，其余第二版再加。

第一版包含：
- `lifecycle_stage` 所处阶段（用户自己选：想了解一下 / 申请人 / 在读 / 校友）
- `academic_background` 学术背景
- `tech_level` 技术基础
- `gmat` / `gre`
- 语言成绩（`toefl` / `ielts`）
- `target_role`（raw + std）
- 时间线两字段（`application_term` / `intake_year`，按阶段填其一）

第二版再加：`target_industry`、`work_years`、`school_tier`。

### 决定记录

| 项 | 决定 |
|---|---|
| 标准词表 | 用现有 6 个 career_roles（role_id 待连库确认） |
| 所处阶段来源 | 用户手选（不从对话推断，不依赖 chunk lifecycle_stage 标签） |
| 第一版范围 | 精简 7 字段 |

### 仍待办

- [x] 连库补全 §三 的 6 个 role_id / role_title
- [ ] 与队友确认 Redis 里画像的 key 结构、`user_id` 从哪来（是否需要登录）
