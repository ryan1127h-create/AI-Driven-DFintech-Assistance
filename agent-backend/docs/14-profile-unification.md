# 14 · 用户画像统一方案(背景与理由)

> 状态:**backend 侧已实施**。本文保留为背景与决策理由;
> **字段映射的权威说明已移到 [`02-interface-contracts.md`](02-interface-contracts.md) §6**,
> 两处不一致时以 §6 为准(它是从代码里逐值核对写出来的)。
> 下面标 ⚠️ 的三处仍需要你那侧改动,§八的 5 个确认项仍待你答复。
> 提出 2026-07-30,实施 2026-07-30。

**已实施部分摘要**(细节见 §6):`common/profile.py` 成为唯一权威并新增 11 个可选字段;
`chat.py` 的同名 `UserProfile` 改名 `ChatUserProfile` 且 `stage` 改为对 `LifecycleStage` 校验;
`api2.py` 的 `RecommendationProfile` 删除、静默回退改为报错;新增
`common/profile_adapter.py` 负责与 rag-data schema 双向转换;死文件 `student/api.py` 已删除。
测试 343 → 457。

---

## 一、为什么要统一

统一前项目里有 **4 份互不兼容的用户画像定义**(「现状」列为实施后):

| # | 位置 | 原名称 | 原规模 | 原类型风格 | 现状 |
|---|---|---|---|---|---|
| 1 | `agent-backend/common/profile.py` | `UserProfile` | 17 字段 + 8 枚举 + 5 子对象 | Pydantic 强类型枚举 | **权威**,现 29 字段 |
| 2 | `agent-backend/app/api/chat.py` | `UserProfile`(**与 #1 同名**) | 2 字段 | 裸 `str` | 改名 `ChatUserProfile`,仅作传输 DTO,`stage` 对 `LifecycleStage` 校验 |
| 3 | `agent-backend/student/api2.py` | `RecommendationProfile` | 9 字段 | 全裸 `str` | 已删除,改为权威词表类型的 `RecommendationProfileInput` |
| 4 | `rag-data/docs/user_profile_schema.md` + `scripts/profile_extract.py` | 文档 schema | ~18 字段 | 嵌套 `{raw, std}` | **未改动**(你的目录),由 `common/profile_adapter.py` 双向对接 |

#1 和 #2 曾**同名但毫无关系**——一个 17 字段强类型,一个 2 字段裸 str,任何人写
`from ... import UserProfile` 都得先确认是哪一个。这正是 #2 被改名的原因。

两条链路目前**完全不相交**,所以画像不一致还没造成线上故障:

- `chat.py` 的 `user_stage` → `app/agents/supervisor.py`(LangGraph)→ academic / admissions / financial / knowledge
- MVP#4–#7 四个 agent → `agent-backend/supervisor.py` 的 `_ROUTES` → 吃 `common/profile.py`

**一旦把聊天链路接到 #4–#7,画像就会立刻出问题。** 统一前唯一的桥 `student/api2.py` 是这样写的:

```python
# 统一前 —— 此行已删除
stage = _enum_value(LifecycleStage, incoming.lifecycle_stage) or LifecycleStage.current
```

任何不认识的阶段值**静默变成"在读"**。传 `enrolled` 或 `student` 碰巧语义对上了,但传一个拼错的 `alumnus` 也会变成 `current`,于是 checklist 和 tracker 会按"在读学生"给一位校友出建议。这类无声的错误数据比直接报错危险得多。

**现在**:`RecommendationProfileInput.lifecycle_stage` 的类型就是 `LifecycleStage`,不认识的值由
Pydantic 直接拒绝(422,回显收到的原值),`_enum_value` 这个强制转换辅助函数已从全仓库消除。
同类的静默压缩在 `student/profile_form.py` 的 `normalize_stage` 里还有一处(把除 `current` 以外
的一切都压成 `applicant`),也已一并修掉。

**结论**:以 `common/profile.py` 的 `UserProfile` 为唯一权威定义,另外三份收敛过去。

---

## 二、统一后的 `lifecycle_stage` 词表 ⚠️

这是**唯一需要你改代码**的词表。三套现状:

| 来源 | 值 |
|---|---|
| `common/profile.py` `LifecycleStage`(权威) | `prospect` / `applicant` / `admitted` / **`current`** / **`graduating`** / `alumni` |
| `chat.py:22` 注释、`app/agents/supervisor.py:33` 注释 | `prospect` / `applicant` / `admitted` / **`student`** / `alumni` |
| `rag-data/scripts/profile_extract.py:55` `LIFECYCLE_STAGES` | `prospect` / `applicant` / `admitted` / **`enrolled`** / `alumni` |

「在读」这一个状态,三处用了三个不同的词:`current` / `student` / `enrolled`。

### 采用的词表(6 值)

```python
prospect     # 想了解一下
applicant    # 申请中
admitted     # 已录取、未入学
current      # 在读            ← 你的 enrolled / student 对应这个
graduating   # 即将毕业        ← 新增,你那两套都没有
alumni       # 校友
```

**为什么选 `current` 而不是你的 `enrolled`**:说实话 `enrolled` 的语义更准确,和 `admitted` 的对比也更清楚(你文档里那句「⚠️ `admitted` 与 `enrolled` 是两个不同阶段,别混」我完全同意)。选 `current` 纯粹是因为它已经贯穿了 MVP#4–#7 四个模块、`common/mock_data.py` 的 5 个 profile、以及全部 300 多个测试,改名的波及面比你那侧大一个量级。**如果你觉得 `enrolled` 更值得坚持,这条可以谈** —— 代价是我这侧要做一次全量改名。

**为什么必须加 `graduating`**:MVP#5 的毕业提醒需要一个状态来挂载。只有 `current` 和 `alumni` 的话,「即将毕业、该选毕业设计了」这类提醒没有触发点。

### 你需要改的

1. `rag-data/scripts/profile_extract.py:55`
   ```python
   # 改前
   LIFECYCLE_STAGES = ["prospect", "applicant", "admitted", "enrolled", "alumni"]
   # 改后
   LIFECYCLE_STAGES = ["prospect", "applicant", "admitted", "current", "graduating", "alumni"]
   ```
2. `rag-data/docs/user_profile_schema.md:60` 的枚举说明同步(含新增 `graduating` 的语义描述)
3. `app/api/chat.py:22` 与 `app/agents/supervisor.py:33` 的注释同步

我这侧会同时放宽 `student/extract_profile.py:33` 的白名单——它目前只认 `{applicant, current}` 两个值,意味着 prospect / admitted / graduating / alumni 的画像根本无法从简历自动提取。

---

## 三、好消息:目标职业词表完全一致 ✅

你的 `CAREER_ROLES`(`profile_extract.py:44`、schema §三)和我的 `TargetRole` 枚举是**同一组 6 个 id**:

| role_id | role_title |
|---|---|
| `quant_risk` | Quantitative / Risk Analyst |
| `data_analytics` | Financial Data Science / AI |
| `fintech_pm` | FinTech Product Manager |
| `payments` | Payments / Blockchain / Digital Assets |
| `digital_banking` | Digital Banking |
| `compliance_regtech` | Compliance / RegTech |

你文档里写的「零对齐成本」确实成立。**这块你不用动**,唯一差异是结构:你是 `target_role_std` 单值,我是 `target_roles: list[TargetRole]` 多值。适配器负责单值 ↔ 单元素列表的转换,双方代码都不用改。

---

## 四、技术水平字段 ⚠️

| | 你 | 我 |
|---|---|---|
| 字段名 | `tech_level` | `technical_proficiency` |
| 结构 | `{"raw": "会一点 Python", "std": "basic"}` | 扁平枚举 |
| 值域 | `none` / `basic` / **`strong`**(3 级) | `none` / `basic` / **`intermediate`** / **`advanced`**(4 级) |

**采用四级**,适配器把你的 `strong` 映射到 `advanced`。

**为什么不降成三级**:MVP#7 的选课难度过滤依赖这个粒度——`intermediate` 和 `advanced` 合并后,「能不能上硬核课」的判断会变粗,推荐质量下降。

**你需要改的**:`TECH_LEVELS` 加两个值,或者维持三级、由适配器做 `strong → advanced` 的单向映射(此时你侧零改动,但从我这侧回流到你那里时 `intermediate` 会降级成 `basic`,有信息损失)。**这两个方案我都能接受,你选。**

关于 `{raw, std}` 嵌套结构:你保留用户原话这个设计我认为是对的(便于设置页回显、便于审计映射是否准确),所以原话不会被丢弃,你不必扁平化。

**实施时改了承接方式,与本文最初的说法不同,请以这里为准**:原计划给每个字段加可选的
`*_raw` 列,最终实现为**单个 `raw_inputs: dict[str, str]`** —— 避免四个近重复的列,且以后哪个字段
需要留原话都不用再改 schema。**键是权威模型的字段名**(`academic_background`、
`technical_proficiency`、`target_roles`、`target_industry`),不是你那侧的键名(`tech_level`、
`target_role_raw`),转换由适配器负责。你那侧 `EMPTY_PROFILE` 里值为 null 的 raw 会被丢弃而不是
写成空串。两份真实 fixture(`sample_profile_quant.json`、`sample_profile_payments.json`)已做
逐键往返验证,原话按字节保持不变。

---

## 五、个性化开关:这一项会改变默认行为 ⚠️⚠️

| | 你 | 我 |
|---|---|---|
| 字段 | `personalization_opt_out` | `ConsentFlags.personalization` |
| 极性 | opt-**out**(true = 退出) | opt-**in**(true = 同意) |
| 默认值 | `false` → 默认**做**个性化 | `False` → 默认**不做**个性化 |

**两者极性相反,默认行为也相反。** 如果直接按字段名映射 `personalization = personalization_opt_out`,行为会完全颠倒。

**统一为 opt-in、默认关。** 依据是 PDF 需求 §3 对个性化退出的要求,以及 `common/profile.py:151` 的注释所引用的 schema doc §5(privacy-safe default)。

**这会改变你那侧的默认行为:从「默认个性化」变成「默认不个性化」。** 用户不明确同意就不做个性化。这是我特意提出来的一条,因为它不是命名问题而是合规问题——请确认你能接受,以及你那侧是否有已经依赖「默认开」的逻辑。

---

## 六、完整字段对照

### 双方都有

| 概念 | 你(rag-data) | 权威模型 | 处置 |
|---|---|---|---|
| 用户 ID | `user_id` | `user_id: str` | 一致 |
| 阶段 | `lifecycle_stage`(5 值) | `lifecycle_stage: LifecycleStage`(6 值) | ⚠️ 见 §二 |
| 学术背景 | `academic_background: {raw, std}` | `academic_background: AcademicBackground` | `std` → `field_of_study`,`raw` 存入新增可选字段 |
| 技术基础 | `tech_level: {raw, std}`(3 级) | `technical_proficiency: Proficiency`(4 级) | ⚠️ 见 §四 |
| 工作年限 | `work_years: number` | `work_years: int \| None` | 一致 |
| 目标职业 | `target_role_raw` + `target_role_std` | `target_roles: list[TargetRole]` | ✅ 值域一致,仅结构转换 |
| 个性化 | `personalization_opt_out` | `ConsentFlags.personalization` | ⚠️⚠️ 见 §五 |

### 只有你有 → 并入权威模型

全部已并入,且**全部可选、默认空**,所以不影响任何现有调用方。「权威模型实际类型」一列是你那侧
对接时该看的:

| 字段 | 你的类型 | 权威模型实际类型 | 说明 |
|---|---|---|---|
| `intake_year` | enum 2025/2026/2027 | `int \| None`(1000–9999) | 未用枚举:硬编码年份窗口每年都要改代码。仍会拒掉 `25`、`226` 这类 typo。你那侧传字符串 `"2026"`,适配器转 int,回传时再转回字符串 |
| `application_term` | text | `str \| None` | 申请目标学期,如「2026 Fall」 |
| `gmat` / `gre` / `toefl` | number | `int \| None`(≥0) | 只约束非负:GMAT Focus 与旧制分数区间不同,写死一个就是编造数据 |
| `ielts` | number | `float \| None`(≥0) | **必须是 float** —— 用 int 会把 6.5 截断成 6 |
| `asked_topics` | system | `list[str]`,默认 `[]` | 避免重复提问 |
| `updated_at` | system | `str \| None`(ISO 8601) | 沿用本文件既有的日期字符串约定,未做格式校验 |
| `school_tier` | text | `str \| None` | 你第二版才上 |
| `target_industry` | `{raw, std}` | `str \| None` + `raw_inputs` | 未用枚举:你的 std 词表未定,而 `payments`/`crypto` 在我的 `WorkDomain` 里没有对应值,强行枚举会拒掉合法值 |

### 只有我有 → 你无需关心,但别丢

`authenticated`、`email`、`country`、`work_domain`、`finance_knowledge`、`preferred_learning_style`、`application_type`、`completed_modules`、`application`(含 `status_code` / `document_status` / 状态历史)、`notification_prefs`、`notification_log`。

这些服务 MVP#4–#7,你那侧的抽取流程不需要填,适配器会保留原值不动。

### `chat.py` 的 `name` 字段

`app/api/chat.py:23` 有 `name: Optional[str]`,权威模型没有姓名字段。合并时倾向**不并入**——考虑到仓库是 public,姓名属于可直接识别的个人信息,除非有明确用途否则不进画像。如果聊天侧需要称呼用户,建议只在会话内存里保留,不落到画像。**这条也请确认。**

---

## 七、适配器边界约定

改动范围**限于 `agent-backend/` 内的三份合并**,再加一个显式双向适配器对接你的 schema。**不改你的 pipeline 内部逻辑。**

一条硬性约定:**转换失败必须报错,不得静默回退。**

```python
# 现状(api2.py:114)—— 不认识的值静默变成 current
stage = _enum_value(LifecycleStage, incoming.lifecycle_stage) or LifecycleStage.current  # 已删除

# 改为 —— 显式失败,带上收到的原值
raise ProfileMappingError(f"unknown lifecycle_stage: {incoming.lifecycle_stage!r}")
```

理由:静默回退会让错误数据一路流到 checklist / tracker,产出看起来合理但完全错误的建议,而且没有任何日志线索。宁可在边界上炸掉。

---

## 八、需要你确认的 5 件事

1. **`current` vs `enrolled`** —— 接受用 `current`,还是坚持 `enrolled`(我做全量改名)?
2. **`graduating`** —— 你那侧的抽取能否支持这个新状态?
3. **`tech_level`** —— 你加两个值升到四级,还是维持三级、由适配器单向映射(接受 `intermediate` 回流时降级)?
4. **个性化默认值反转** —— 从「默认开」变「默认关」,你那侧是否有依赖旧默认的逻辑?
5. **`name` 字段** —— 同意不并入画像吗?

另外:`docs/02-interface-contracts.md` 的 W1 确认清单目前**六项全未勾选**。这次对齐正好把它一起签掉。

---

## 附:顺带发现的一个 bug(与画像无关,但在同一文件)

`student/api2.py:66`

```python
return {(payload), status}
```

这是 **set 字面量**而不是 tuple,`payload` 是 dict、不可哈希,实测抛 `TypeError: unhashable type: 'dict'`。这是错误处理路径,意味着一旦出错就会二次崩溃,原始错误信息全部丢失。合并时我会一并修掉。
