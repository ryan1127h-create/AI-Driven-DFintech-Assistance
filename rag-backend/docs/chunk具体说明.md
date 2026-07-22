# Chunk 具体说明

本文件逐类说明 chunking 到底在做什么、每张表怎么切、切成什么样。
配合 `docs/RAG_PIPELINE_PLAN.md`（总方案）一起看：总方案讲"为什么"，本文件讲"具体怎么切"。

三类数据对应三种切法（均已完成，合计 **184 chunk**）：
- **A 类**（原子表，147）：1 行 = 1 chunk，字段模板生成 context，不调 LLM
- **B 类**（长文本，31）：按 `#####` 标题切节；超 500 token 的节段落边界二次切（overlap 50）
- **C 类**（关系表，6）：按角色聚合成自足段落；技能标签折进 courses chunk

三类最终都写进同一张 `app.document_chunks`（用 chunk_key 前缀区分：
`course:` / `snippet:` / `rule:` / `admission:` / `status:` / `competitor:` / `page:` / `role:`），
检索时统一搜这一张表。

---

## A 类：原子表切片（scripts/chunk_atomic.py）

### 一句话
把 6 张"每行本身就是一条独立事实"的表，逐行翻译成 AI 能按意思检索到的知识片段，
存进 `app.document_chunks`。

### 为什么这样切
这些表的每一行已经是一个完整、独立的事实（一门课、一条 FAQ、一条规则……），
不需要再切碎，也不该把多行拼在一起。所以 **1 行 = 1 chunk**。
context 用字段模板直接拼，数据规整、结果确定，**不花 LLM 的钱**。

### 覆盖的 6 张表与预期数量

| 表 | 行数 | 每 chunk 代表 |
|---|---|---|
| courses | 72 | 一门课 |
| knowledge_snippets | 39 | 一条 FAQ / 申请说明 |
| course_rules | 13 | 一条培养方案规则 |
| admissions_items | 11 | 一份申请材料 |
| application_status_translations | 7 | 一个申请状态解释 |
| competitor_programs | 4 | 一个竞品项目 |
| **合计** | **146** | |

（数据源是**实时数据库**，不是 CSV 快照——CSV 会被 Supabase 截断到 100 行且不同步删改。）

### 流程 4 步
```
① 读库    从 Supabase 读 6 张表所有行
② 拼文字  每行 → context（说明）+ content（正文）
③ 变向量  送 OpenAI text-embedding-3-small → 1536 维向量
④ 写库    [文字 + 向量 + 标签] 写入 document_chunks（按 chunk_key upsert）
```
实际做 embedding 的输入 = `context + "\n" + content`（Anthropic 上下文检索思路）。

### context 与 content 的区别（关键）
每行拼成两段：
- **content**：真正的答案内容
- **context**：一句"这段讲什么、能回答什么问题"的说明前缀 —— 显著提升检索命中率

以 FT5005 为例：
```
context: This describes course FT5005 "Machine Learning for Finance", a 4-unit
         course relevant to NUS MSc DFinTech. Useful for questions about this
         course's content, prerequisites, and course recommendation.
content: FT5005 Machine Learning for Finance (4 units). Faculty: Computing...
         Description: This course covers foundation knowledge in machine learning...
```

### 每张表的模板
| 表 | content 拼法 |
|---|---|
| courses | 代码 + 标题 + 学分 + 院系 + 简介 + 先修 + preclusion |
| knowledge_snippets | FAQ / 申请说明原文（text 字段） |
| course_rules | 培养方案规则原文（text 字段） |
| admissions_items | 材料名 + 是否必交 + 说明 |
| application_status_translations | 状态人话 + 下一步 + 预计天数 |
| competitor_programs | 项目名 + 各维度（学费/学制/GMAT/课程重点…） |

### 附带写入的标签
- **answer_type**：`official`（官方事实）/ `advisory`（建议/推断）。竞品对比标 advisory；其余多为 official。对应 PDF"区分核实事实与 AI 推断"的要求。
- **conflict_group**：GMAT 冲突处理。`knowledge_snippets` 里的 FAQ 分数线那条标 `test_score_requirement` + `authoritative=true`（FAQ 为准）；招生页那条 650 在 B 类标同组 + `authoritative=false`。
- **metadata**（jsonb）：intake 届别、是否必交、来源链接、can_recommend 等，供检索前过滤。
- **chunk_key**：稳定唯一 ID，如 `course:FT5005`、`snippet:faq_web_...`、`rule:cur_...`。upsert 依据，重跑不会重复。

### 两种运行方式
```bash
# 只拼文字并打印，不调 OpenAI、不写库（先看质量）
python scripts/chunk_atomic.py --dry-run

# 只处理一张表（调试用）
python scripts/chunk_atomic.py --only courses

# 全量：embedding + 写库
python scripts/chunk_atomic.py
```
跑完 `document_chunks` 应为 146 行。成本约 ¥0.01。

---



## B 类：长文本切片（scripts/chunk_pages.py）

### 一句话
把 `programme_pages` 里的长页面正文，按标题切成小节；太长的小节再二次切；
每个 chunk 加"上下文前缀"后 embedding，存进 `document_chunks`。

### 为什么这样切
一整页正文（几千字符）不能当一个 chunk —— 太大，检索不准、答案不聚焦。
但这些页面有清晰的 markdown 标题（`#####`），标题天然就是语义边界，
所以**按标题切**即可，不必上昂贵的 embedding 语义切分。

### 覆盖范围：5 页（跳过 FAQ）
数据源 = `app.programme_pages` 表中 `rag_include=true` 的页面，**但排除 page_07 (FAQ)**
—— FAQ 的 27 条问答已在 A 类（knowledge_snippets 的 faq_web）切过，重切会重复。

| page_id | 页面 | 正文字符 | 标题数 |
|---|---|---|---|
| page_02 | Programme Overview      | ~6,300 | 10 |
| page_03 | Capstone Project        | ~8,200 | 9  |
| page_04 | Admission Requirements  | ~2,400 | 3  |
| page_05 | Application Information | ~6,700 | 6  |
| page_06 | Fees and Scholarships   | ~3,900 | 5  |

### 切分规则（一套统一逻辑）
```
每页正文
① 按 ##### 标题切成节 (section)
② 每节判断长度（按 token 数，不是字符数）：
     ≤ 500 token  → 整节 = 1 个 chunk（大部分节属于这种）
     > 500 token  → 在段落边界(空行)处二次切，每块 ~500 token，overlap 50 token
③ 每个 chunk 加 context 前缀（见下）
④ context + content 一起 embedding
⑤ 写进 document_chunks（chunk_key 前缀 page:）
```
> 注意 500 是 **token**（≈ 350-400 英文词 ≈ 2000 字符），判断超长用 token 换算。

### 已知的两个超长节（会触发二次切）
| 页面 | 小节 | 字符 | 处理 |
|---|---|---|---|
| page_03 | Procedure to post an internship | 3,685 | 二次切 |
| page_05 | Submission of Application（文件清单大表格） | 5,018 | 二次切 |

（page_02 的 Course Plan 1463字、page_06 的 Fees 1960字略长，是否二次切由 token 阈值决定。）

### 上下文嵌入（Contextual Retrieval）—— B 类的重点
页面切出来的小节常常"缺上下文"：比如 Fees 页切出的 Fees 节只写
"tuition fees is S$74,120..."，没提这是**哪个项目**的学费，用户问
"NUS DFT 学费多少"可能匹配不上。给每个 chunk 加一段 context 前缀解决此问题
（Anthropic 报告此法使 top-20 检索失败率平均降低 35%）。

两种生成方式，**B 类第一版用方式 A，如果有预算 会考虑用B**：
- **方式 A（模板，省钱，采用）**：context = 页面标题 + 项目名，例：
  `"This section is from the Fees and Scholarships page of the NUS MSc DFinTech programme."`
- **方式 B（LLM 生成，Anthropic 原版，暂不用）**：让 LLM 读整页+该节生成最贴切的 context，更精准但每 chunk 调一次 LLM。留待评估后按需对个别页面启用。

> 模板版即可拿到那 35% 提升的大部分 —— 关键是让 chunk 知道自己属于哪页/哪个项目。

### 标签（与 A 类一致）
- **answer_type**：页面正文多为 `official`
- **conflict_group**：page_04 Admission 的 Test Scores 节含 "minimum GMAT 650"，
  标 `test_score_requirement` + `authoritative=false`（按 GMAT 决策，FAQ 为准）
- **metadata**：page_id、page_label、section_title、source_url、risk_level
- **chunk_key**：如 `page:page_06:2`（页 + 第几节/块），upsert 依据

### 运行方式
```bash
python scripts/chunk_pages.py --dry-run      # 打印切出的节/块，不写库
python scripts/chunk_pages.py --only page_06  # 单页调试
python scripts/chunk_pages.py                # embedding + 写库
```
预计新增 30-40 个 chunk，追加进 document_chunks（A 类 147 + B 类 ≈ 180+）。

---

## C 类：关系表切片（scripts/chunk_relationalC类.py）

### 一句话
把"职业角色 ↔ 推荐课程 ↔ 技能"这几张关系表，**按角色聚合**成 6 个自足的
career chunk；技能信息另外**折进 courses chunk**，不单独成 chunk。

### 为什么这样切
关系表的单独一行（如 `role_id=quant_risk, course_code=FT5005`）对检索毫无意义
——没有上下文、无法独立回答任何问题。必须**聚合**成一段自然语言才有价值。

### 涉及的 4 张表与处置

| 表 | 行数 | 怎么处理 |
|---|---|---|
| `career_roles` | 6 | ✅ **每个角色 1 chunk**（主体） |
| `career_role_modules` | 44 | ❌ 不单独切 —— 内容已含在 `career_roles.raw.recommended_modules` 里，重复 |
| `module_skills` | 173 | ❌ 不单独切 —— 折进 courses chunk（见下"方案 2"） |
| `skills` | 9 | ❌ 不单独切 —— 用作技能标签的字典（label + aliases） |

**产出：6 个 chunk**（`role:quant_risk`、`role:fintech_pm` …）

> 数据完整性已核对：`module_skills` 用到的 9 个 skill_id 在 `skills` 表中全部有定义，无孤儿引用。

### 角色 chunk 怎么拼
`career_roles` 一张表就够 —— 它的 `raw` 里已经带了 `recommended_modules`。
每个角色聚合成：**角色全名 + 关键技能 + 推荐课程**。

例（quant_risk）：
```
context: This describes the "Quantitative / Risk Analyst" career track in the
         NUS MSc DFinTech. Useful for questions about career paths, which
         courses to take for a target job role, and skill requirements.
content: Career track: Quantitative / Risk Analyst (quant_risk) ... Key skills:
         Risk modelling (quantitative risk, 风险量化); Data analytics (数据科学);
         Finance knowledge (金融); Programming (编程). Recommended modules:
         BT4016 Risk Analytics..., BT4013..., FT5010..., FT5005... (8 门)
```

`answer_type = advisory` —— 职业建议属于推荐/推断，不是官方政策。

### 方案 2：技能标签折进 courses chunk（跨类改动）
除了 6 个角色 chunk，还把 `module_skills` + `skills` 的技能信息
**补进 A 类已有的 72 个 courses chunk**（不新增 chunk，只让课程 chunk 更丰富）。

做法：`chunk_atomicA类.py` 里 `load_course_skills()` 查 module_skills ⋈ skills，
给每门课的 content 追加一行：
```
FT5005 Machine Learning for Finance (4 units). ... Description: ...
Skills covered: AI / Machine Learning (machine learning, artificial intelligence, 机器学习);
Data analytics (data analysis, analytics, 数据科学); Finance knowledge (finance, 金融);
Programming (software development, coding, 编程).
```
改完需重跑：`python scripts/chunk_atomicA类.py --only courses`（upsert 更新，72 行数量不变）。

### 为什么技能标签要带中文别名
语料是英文，但用户会用中文提问。`skills` 表每个技能自带中英别名
（`机器学习`/`风险量化`/`区块链`…），把别名一起拼进 chunk，等于
**在英文资料里主动埋中文锚点** —— 中文提问可直接命中，不必完全依赖跨语言向量。

实测有效：中文问「哪些课教机器学习？」→ 命中 CS5339、FT5005（这些课的官方描述里
并不一定含"machine learning"字样，是技能标签帮它们被搜到的）。

### 运行方式
```bash
python scripts/chunk_relationalC类.py --dry-run   # 打印 6 个角色 chunk
python scripts/chunk_relationalC类.py             # embedding + 写库
```
产出 6 chunk。合计：A 147 + B 31 + C 6 = **184 chunk**。

### 检索验证（scripts/test_search.py）
| 问题 | Top1 | 相似度 |
|---|---|---|
| I want to become a FinTech product manager, which courses? | `role:fintech_pm` | 0.707 |
| Which courses to become a quantitative risk analyst? | `role:quant_risk` | 0.623 |
| 想做量化风险分析师应该学什么课？ | BT4016 + `role:quant_risk` | 0.545 |
| 哪些课教机器学习？（验证方案 2） | `course:CS5339` | 0.502 |
