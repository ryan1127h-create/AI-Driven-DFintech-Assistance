# NUS MSc DFT — RAG Pipeline 完整方案

本文件是 chunking + 检索 pipeline 的**总设计**：技术选型、整体流程、执行进度。

配套细节文档：
- `docs/chunk具体说明.md` — A/B/C 三类切片各怎么切、为什么
- `docs/BM25+RRF+Rerank具体说明.md` — 检索四层各在干什么、为什么这么选
- `README.md` — 环境配置、脚本用法

---

## 0. 模型与技术选型（已定）

| 环节 | 选型 | 说明 |
|---|---|---|
| Embedding | **OpenAI text-embedding-3-small（1536 维）** | 8GB 内存跑不动本地 BGE-m3；API 极便宜（全量 < ¥1） |
| 关键词检索 | **rank_bm25（Python 内存版）** | 语料仅 ~180 chunk，无需数据库 BM25 扩展 |
| 融合 | **RRF（Reciprocal Rank Fusion）** | 无需调参 |
| 精排 | **Cohere `rerank-multilingual-v3.0`** | 不吃内存（API）；Trial key 免费每月 1000 次；多语言覆盖中文提问 |
| 回答 LLM | **未定，与 embedding 无关** | 可继续用免费/DeepSeek；到 Step 8 接入时再定 |

> Embedding 只负责"把文字变坐标、按意思找资料"；回答 LLM 是另一笔账，后面才规划。

---

## 1. 源数据 → 三类切分策略（核心）

原则：**大部分数据已是"原子片段"，不要盲目按固定长度硬切。** 按数据形态分三类。

### A 类：原子表 → 1 行 = 1 chunk（不切分，模板生成 context）
| 表 | 行数 | 每 chunk |
|---|---|---|
| courses | 72 | 一门课 |
| knowledge_snippets | 39 | 一条 FAQ / 申请材料说明 |
| course_rules | 13 | 一条培养方案规则 |
| admissions_items | 11 | 一条招生要求 |
| competitor_programs | 5 | 一个竞品项目 |
| application_status_translations | 8 | 一条状态解释 |

context 用**字段模板拼**，不调 LLM。例：
```
[context] This describes course FT5005 "Machine Learning for Finance",
          a 4-unit MSc DFinTech course. Useful for questions about machine
          learning, AI, course recommendation, curriculum.
[content] FT5005 Machine Learning for Finance (4 units). Description: ...
          Prerequisite: ...
```

### B 类：长页面正文 → 按标题结构切分
| 表 | 范围 | 切法 |
|---|---|---|
| programme_pages | rag_include=true 的 6 页 | 按 markdown 标题（`#####`）切，每节一个 chunk |

- 目标 **300–500 token / chunk**，overlap ~50 token
- 某节过长又无子标题时，才在节内二次切
- context = 模板 + 页面标题（"本段来自 Fees and Scholarships 页"）
- **不上 embedding 语义切分**：页面已有清晰标题，结构切分效果几乎一样且免费。留待以后处理无结构长文时再用。

### C 类：关系表 → 聚合成一句话再做 1 chunk
| 表 | 聚合方式 |
|---|---|
| career_roles + career_role_modules + module_skills + skills | 每个角色一个 chunk，把推荐课程 + 关键技能拼进去 |

例：
```
For the Quantitative Risk Analyst role, recommended modules include
FT5005 Machine Learning for Finance, FE5108 Portfolio Theory...;
key skills: Python, risk modeling, time-series analysis.
```

**预计总 chunk 数 ≈ 180**（小语料，印证 BM25 内存版足够）。

---

## 2. document_chunks 表设计

```sql
create table if not exists app.document_chunks (
  id            bigint generated always as identity primary key,
  chunk_key     text unique not null,     -- 稳定ID: 'course:FT5005' / 'page:page_06:2'
  source_table  text not null,            -- courses/knowledge_snippets/course_rules/programme_pages/career_roles
  source_id     text not null,            -- 原始行主键
  content       text not null,            -- chunk 正文
  context       text,                     -- 模板/LLM 生成的上下文前缀
  embedding     vector(1536),             -- OpenAI 3-small
  token_count   int,
  answer_type   text,                     -- official / advisory / recommendation
  conflict_group text,                    -- 冲突分组，如 'test_score_requirement'（GMAT 决策）
  authoritative boolean not null default true,  -- 冲突时以谁为准
  metadata      jsonb not null default '{}',    -- intake / lifecycle_stage / source_url / can_recommend / risk_level
  import_run_id bigint,
  created_at    timestamptz not null default now()
);

create index on app.document_chunks using hnsw (embedding vector_cosine_ops);

alter table app.document_chunks enable row level security;
-- 内部表，不给 anon；走后端 RAG API
```

实际做 embedding 的输入 = `context + "\n" + content`（Anthropic Contextual Retrieval 思路）。

### 冲突处理（落实 GMAT 决策）
- 招生页"最低 GMAT 650"与 FAQ"无最低线/一般 700"矛盾 → 两个 chunk 都打 `conflict_group='test_score_requirement'`
- FAQ 那条 `authoritative=true`，招生页那条 `false`
- 检索命中其一 → 同组一起取出 → 回答时呈现两种说法并建议咨询招生办
- **绝不修改招生页原文**

---

## 3. 检索层（4 层）— ✅ 已实现 `scripts/retrieval.py`

```
用户问题
   │
   ├─ ① 向量检索 (dense)   → pgvector 余弦相似度，取 RECALL_K=50
   ├─ ② 关键词检索 (BM25)  → rank_bm25 内存版，取 RECALL_K=50
   ├─ ③ Rank Fusion (RRF)  → 加权倒数排名融合（语义 0.8 / BM25 0.2）
   └─ ④ Rerank             → Cohere 精排融合结果 → top-5
```

**RECALL_K=50 是算过的**：cookbook 用 150/737≈20%，我们 50/184≈27% 比例相当。
照抄 150 会捞出 184 条里的 81%，等于不筛选，①②排序完全失去意义。

细节见 `docs/BM25+RRF+Rerank具体说明.md`。

**实测效果**（个案，非统计结论）：
| 问题 | ① 只向量 | ①②③ | ①②③④ |
|---|---|---|---|
| "NUS和NTU比怎么样?" | 不相关的 Test Scores 排第2 ❌ | 仍第2 ❌ | **被压出 top5** ✅ |
| "想做量化风险分析师学什么课?"（中文）| role:quant_risk 第2 | 仍第2 | **顶到第1（0.997）** ✅ |

- 检索前可按 `metadata` 过滤（如按学生 `intake` 过滤 course_rules，避免两届串）— 待实现

---

## 4. 评估（Step 7）

- **50-80 个测试问题**（不是 30 —— 30 题时 1 题 = 3.3pp，95% 置信区间达 ±11pp，
  测不出小改进；50-80 题可把分辨率降到 1.3-2pp）
- 每题标注 golden_chunk / 标准答案 / 期望 answer_type
- 覆盖：8 个数据源 × 6 个生命周期阶段 × 中英文各半 + 冲突案例 + 边界情况
- 指标：**Pass@5/10/20**（先调这个到 >0.9）、Answer accuracy、Groundedness（防幻觉）
  - Pass@k 不需要回答 LLM，可先做
  - Answer accuracy / Groundedness 需接回答 LLM（Step 8 后）
- ⚠️ 出题陷阱：AI 从 chunk 反向生成的问题会用 chunk 原词，导致分数虚高（"照答案出题"）。
  必须人工改写成申请人口语；中文题天然避开此问题。

---

## 5. 执行顺序（Step by Step）

- [x] Step 1 连接 Supabase
- [x] Step 2 补齐 + 清洗源数据
- [x] **Step 3a** 验证 OpenAI key（1536 维确认）
- [x] **Step 3b** 建 document_chunks 表（pgvector + HNSW 索引）
- [x] **Step 4** A 类切片 → 147 chunk（6 张原子表）
- [x] **Step 5** B 类 31 chunk（页面正文按标题切）+ C 类 6 chunk（角色聚合）
      → **document_chunks = 184 行，切片阶段完成**
- [x] **Step 6** 检索层：向量 + BM25 + RRF + Cohere rerank → `scripts/retrieval.py`
- [x] **Step 7** 65 题评估集 + Pass@k + 消融对比 → `data/eval_set.jsonl`、`scripts/evaluate.py`

**数据层与检索层已完成。当前位置：Step 8 接回答 LLM。**

---

### Step 7 结果（60 道有答案题）

| 检索配置 | Pass@5 | Pass@10 | Pass@20 |
|---|---|---|---|
| ① 仅向量（基线） | 95.0% | 96.7% | 98.3% |
| ①②③ +BM25+RRF | 95.0% | 98.3% | 98.3% |
| ①②③④ +Rerank | 96.7% | 98.3% | 98.3% |

中文题（17 题）：向量 94.1% → 加 BM25 后 **100%**，验证"中文别名 + BM25 逐字分词"对跨语言的价值。

**客观结论（报告口径）**：
- 基线已达 96.7%，**上下文嵌入 + 结构化切片是性能主因**
- 后三层边际收益仅 +1.7pp，且 60 题时 1 题 ≈ 1.7pp，**统计上接近噪声，无法确认显著性**
- 评估集偏事实型（向量本就擅长）；后三层的真实价值在**复杂/模糊查询与排名质量**上，当前评估集测不出
- 评估**发现了一个真实数据盲区**：q37「申请材料要什么格式」检索不到 —— B 类切片时为去重整节跳过 page_05
  的 Submission 节，误删了其中独家的「PDF 格式 / 英文 / 认证翻译件」说明（admissions_items 只列材料、不含格式）

**已评估但暂不采用**：
- LambdaMART 等 learning-to-rank —— 需数千条标注训练数据，与本项目规模不匹配；Cohere 预训练 cross-encoder 更合适
- 分级检索（简单问题跳过 rerank）—— 当前 Pass@5 向量已 95%，且 rerank 的 100-200ms 淹没在 LLM 生成的 1-3s 里，属过早优化

---

### Step 8 — 接回答 LLM ← **下一步**

| # | 任务 |
|---|---|
| 8-1 | 选回答模型（候选：DeepSeek 等免费/低成本方案；与 embedding 供应商无关） |
| 8-2 | 写 Prompt：把检索到的 chunk 喂给 LLM，约束「只用给定资料回答、不许编」 |
| 8-3 | 来源引用：答案带出 `metadata.source_url`（PDF 要求 surface source references） |
| 8-4 | 冲突呈现：读 `conflict_group` / `authoritative`，以 FAQ 为准但提示存在分歧 |
| 8-5 | answer_type 标注：区分 official（官方事实）/ advisory（建议推断） |

### Step 9 — 补完评估（依赖 Step 8）

| # | 任务 |
|---|---|
| 9-1 | **Faithfulness**（幻觉率）：答案每句能否在检索内容中找到依据 |
| 9-2 | **Answer Accuracy**：答案与标准答案是否一致（LLM-as-judge） |
| 9-3 | 无答案题验证：`data/eval_set.jsonl` 的 n01–n05，测没资料时会不会瞎编 |
| 9-4 | 扩充难题评估集：复杂/多条件/更多中文题，提高统计分辨率 |

> 术语对照：RAGAS 的 **Context Recall** ≈ 我们的 **Pass@k**（已做）；**Faithfulness** 待 Step 9。

### Step 10 — Query 改写 / 问题分解（依赖 Step 8）

| # | 任务 |
|---|---|
| 10-1 | 问题分解：「我 GMAT 680、双非金融、想做量化该选什么课」→ 拆成 3 个子问题分别检索再汇总 |
| 10-2 | 查询改写：口语/模糊问题改写成利于检索的形式；中文问题可选翻译改写 |
| 10-3 | 用 9-4 的难题集量化提升（当前简单评估集上无提升，测不出价值） |

### Step 11 — 多轮对话与上下文管理

| # | 任务 |
|---|---|
| 11-1 | 会话状态存储（对话历史） |
| 11-2 | 指代消解：「那它的学费呢」→「它」指上一轮的项目 |
| 11-3 | 历史裁剪：避免上下文无限增长导致成本失控 |
| 11-4 | 生命周期个性化：按 prospect / applicant / student / alumni 给不同答案 |

### Step 12 — 后端 API

| # | 任务 |
|---|---|
| 12-1 | 封装 HTTP 接口供前端调用（前端不直连数据库） |
| 12-2 | 密钥只留后端；RLS 已配置（内部表不对 anon 开放） |

### 穿插待办（不占独立 Step）

- 🔧 修复数据盲区：page_05 Submission 节的格式说明（改 B 类脚本，只跳过重复表格、保留格式段落后重跑）
- 📊 数据更新机制：官网学费/截止日会变，需人工审核 + 半自动更新流程
- 📝 报告与答辩材料（阶段报告已生成于桌面）

### 优先级

- **必做主线**：Step 8 → 9 → 12
- **加分项**：Step 10、11
- **看时间**：9-4 难题集扩充

---

切片成果（详见 `docs/chunk具体说明.md`）：
| 来源 | chunk | 类 |
|---|---|---|
| courses | 72 | A（含技能标签）|
| knowledge_snippets | 39 | A |
| programme_pages | 31 | B |
| course_rules | 13 | A |
| admissions_items | 11 | A |
| application_status_translations | 8 | A |
| career_roles | 6 | C |
| competitor_programs | 4 | A |
| **合计** | **184** | |

Step 6 已修复此前纯向量的两个短板（个案验证，见 `docs/BM25+RRF+Rerank具体说明.md`）：
- "表面相似但不相关"挤进 top3（问竞品对比时 Test Scores 节挤入）→ **rerank 已压出 top5** ✅
- 中文提问角色 chunk 排名偏低 → **rerank 顶到第 1（0.997）**，BM25 也让中文 Pass@10 达 100% ✅
