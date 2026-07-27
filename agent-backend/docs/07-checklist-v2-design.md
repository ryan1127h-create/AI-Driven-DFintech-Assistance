# Technical Design — Checklist v2 (#4 深化)

> **状态**:设计草案 · 已确认 · 配套 [schema](01-user-profile-schema.md)
> **铁律不变**:裁决在纯 Python 规则引擎;LLM 只批量改写解释,不做判断。

四项深化整合为一套:① 扩展规则覆盖 ② 批量解释(性能)③ 文档状态细化 ④ 截止/紧急度联动。

## 1. Profile 新增字段
- `AcademicBackground.degree_classification`(可选 enum):`first | second_upper | second_lower | third | pass | unknown`
- `Application.document_status`(可选 `dict[str,str]`):code → `submitted | under_review | verified | rejected`。`submitted_documents` 保留,视为 `submitted`(向后兼容)。

## 2. 规则引擎 v2(`agents/checklist/engine.py`)
- **新条件** `degree_classification_below`:申请人学位等级**严格低于**给定等级 → 该条件成立(用有序排名比较;`unknown`/缺省视为不触发)。登记进 `admin/schemas.py::SUPPORTED_CONDITIONS`。
- **状态解析**:`document_status[code]` 优先;否则 `code in submitted_documents → submitted`;否则 `missing`。
- **待办判定**:`missing` 与 `rejected` 计入 `outstanding_count`(需要申请人行动);`under_review/verified/submitted` 不算待办。
- **截止/紧急度**:规则项可带 `deadline_key` → 引擎查 `application.deadlines[deadline_key]`,按 `today` 算 `days_left` 与 `urgency`(`urgent ≤3d / soon ≤7d / info`),仅对待办项计算。

`ChecklistItem` 增加字段:`status`(细化)、`deadline`(ISO|None)、`urgency`(None|info|soon|urgent)。

## 3. 规则数据 v2(`data/admissions_rules.json`)
- 新增基础项:`recommendation_letters`(2 封)、`application_fee`。
- 新增条件项:低学位等级 → `academic_justification`(用 `degree_classification_below`)。
- 给项加可选 `deadline_key`(多数指向 `application_deadline`)。
- 新增 `classification_order` 列表(供引擎排序比较)。

## 4. Agent v2(`agents/checklist/agent.py`)
- **批量解释**:把所有 item 的 `{label, why}` 一次性发给 DeepSeek,返回 `{key: 人话}`;无 key 或出错 → 回退到各自 `why`。由 N 次调用降为 1 次。
- 输出 `data`:每项含 `status / deadline / urgency / why`;新增 `outstanding_count`;`speakable` 汇总待办数 + 最紧急项。
- escalation 行为不变(未知条件 → 转人工)。

## 5. 渲染与数据
- `common/mock_data.py`:加/扩一个 profile,带 `degree_classification` + `document_status` + `application.deadlines`,演示新特性。
- `student/templates/results.html`:清单区显示富状态徽章 + 截止日期/紧急度。

## 6. 共享
- 紧急度计算抽成小工具(`agents/checklist/engine.py` 内),与 #5 reminders 的分桶口径一致(≤3 urgent / ≤7 soon)。

## 7. 验证
扩展 `tests/test_checklist.py`:新条件触发、文档富状态、待办计数、紧急度分桶、批量解释离线回退;全离线确定性;原有用例同步更新。
