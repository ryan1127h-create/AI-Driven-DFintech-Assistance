# Technical Design — 模块 #4–#7 可运行 Agent

> **状态**:设计草案 · 配套 [`01-user-profile-schema.md`](01-user-profile-schema.md) / [`02-interface-contracts.md`](02-interface-contracts.md)
> **架构选型**:方案 A —— 共享底座 + 4 个独立 agent + 薄 supervisor
> **技术栈**:Python 3.11 · pydantic v2 · 规则引擎纯 Python · LLM = DeepSeek(OpenAI 兼容)
> **数据**:实验用虚拟数据(`common/mock_data.py` 生成)

---

## 1. 设计原则(贯穿 4 块)

1. **裁决归规则,叙述归 LLM**:资格/缺失项/状态/推荐结论由纯 Python 规则引擎确定性产出;DeepSeek 只把结果"翻译成人话/写 narrative",**不做判断**。
2. **统一数据入口**:所有 agent 只吃 `UserProfile`(schema 文档),输出统一信封(契约文档 §1.3)。
3. **可独立运行与测试**:每个 agent 是一个纯函数式入口 `handle(request) -> Envelope`,不依赖外部网络即可跑(LLM 层可降级为模板文本,便于无 key 测试)。
4. **外部系统全 mock**:招生/CRM 等接口用本地 mock,形状对齐真实 API,后期可替换。

---

## 2. 目录结构

```
capstone/
├─ common/
│   ├─ profile.py      # UserProfile, Enums (pydantic)
│   ├─ envelope.py     # AgentResponse 统一信封 + EscalationRequest
│   ├─ llm.py          # DeepSeek 客户端封装 (可配置/可降级)
│   └─ mock_data.py    # 虚拟 profile / application 生成
├─ agents/
│   ├─ checklist/      # #4
│   ├─ tracker/        # #5
│   ├─ comparator/     # #6
│   └─ navigator/      # #7
├─ data/              # 静态知识: 招生规则、竞品数据集、岗位-模块映射 (JSON/YAML)
├─ supervisor.py      # intent -> agent 路由 (模拟队友对话模块)
├─ run.py             # CLI 演示入口
└─ tests/             # 每个 agent 的确定性测试
```

---

## 3. 共享底座(common/)

### 3.1 `profile.py`
按 schema 文档实现 `UserProfile`、各 Enum、`Application` 子对象。pydantic 负责校验与缺省。

### 3.2 `envelope.py`
```python
class AgentResponse(BaseModel):
    status: Literal["ok","need_clarification","escalated","error"]
    answer_type: Literal["official","advisory","recommendation"]
    speakable: str
    data: dict
    sources: list[str] = []
    missing_fields: list[str] = []
    escalation: EscalationRequest | None = None
```

### 3.3 `llm.py` — DeepSeek 封装
- OpenAI 兼容客户端:`base_url=https://api.deepseek.com`,`api_key=env(DEEPSEEK_API_KEY)`,`model=env(DEEPSEEK_MODEL, default "deepseek-chat")`。
- 单一函数 `explain(system, user) -> str`,低温度。
- **降级模式**:无 API key 时返回基于模板的确定性文本,保证 agent 离线可跑、测试不依赖网络。

### 3.4 `mock_data.py`
生成多样化虚拟 `UserProfile`(不同背景/岗位/阶段)与 `Application` 状态,供 demo 和测试。

---

## 4. 各 Agent 设计

### #4 Checklist Agent(`agents/checklist/`)
- **职责**:据 profile 生成个性化材料清单 + 标注缺失项。
- **规则引擎**:`data/admissions_rules.json` 定义"基础材料 + 条件材料"(条件如:非本地学历需 transcript 评估、工作<2年需补充说明)。引擎据 profile 求值出 `required items` 与 `status(submitted/missing)`。
- **LLM 层**:仅为每条 item 生成 `why`(人话解释)。
- **Escalation**:规则表无匹配条目(如特殊学历)→ 产出 `EscalationRequest(reason=exception_case)`。
- **输出 data**:契约文档 §4 `#4` 格式。

### #5 Tracker Agent(`agents/tracker/`)
- **职责**:查申请状态(人话化)+ reminder 逻辑。
- **Mock 状态机**:`DRAFT→SUBMITTED→UNDER_REVIEW→{OFFER|DOCS_REQUIRED|...}`,提供 `get_status(application_id)`。
- **状态翻译层**:原始 `status_code` → `human_status` + `next_step`(纯规则映射表)。
- **Reminder**:基于 deadlines + `consent_flags.reminders` 生成提醒列表,带频控(同一提醒不重复)与偏好开关。
- **输出 data**:契约文档 §4 `#5` 格式。

### #6 Comparator Agent(`agents/comparator/`)
- **职责**:与竞品项目做客观维度对比 + 基于用户目标的叙述。
- **数据**:`data/programs_dataset.json` —— 人工审核的结构化数据(6 维:curriculum_focus / duration / format / fees / technical_depth / typical_profile)。
- **规则层**:据 `target_roles` 计算"best for you"匹配(确定性打分,非排名)。
- **LLM 层**:仅基于数据集字段写 narrative。**硬约束**:不生成排名、不杜撰字段、强制带 disclaimer。
- **输出 data**:契约文档 §4 `#6` 格式。

### #7 Navigator Agent(`agents/navigator/`)
- **职责**:据目标岗位推荐模块 + 技能差距 + 解释。
- **数据**:`data/role_module_map.json` —— 6 个岗位 × {所需技能, 推荐模块}。
- **规则层**:岗位→模块映射 + 据 profile 技能字段算 skill gap(确定性)。
- **LLM 层**:仅写 `explanation`(为什么这样推荐)。
- **输出 data**:契约文档 §4 `#7` 格式。

---

## 5. Supervisor 与运行

- `supervisor.py`:`route(request)` 按 `intent`(契约 §1.2 的 7 个)分发到对应 agent。模拟队友的对话/意图模块,便于端到端演示。
- `run.py`:CLI,例如 `python run.py checklist --mock 1`,打印信封 JSON + speakable。

---

## 6. 验证策略

- 每个 agent 配**确定性测试**(`tests/`):固定 mock profile → 断言规则引擎输出(清单项/状态/推荐),**不依赖 LLM**(LLM 走降级模板)。
- 验收对齐契约文档各 `data` 结构 + 原始需求文档的 acceptance criteria。

---

## 7. 实施顺序(依次生成)

1. `common/` 底座(profile / envelope / llm / mock_data)
2. **#4 Checklist**(旗舰,确定性最强)
3. **#5 Tracker**
4. **#6 Comparator**
5. **#7 Navigator**
6. `supervisor.py` + `run.py` + `tests/` 收尾

每完成一块:可独立 `run.py` 演示 + 跑测试。
