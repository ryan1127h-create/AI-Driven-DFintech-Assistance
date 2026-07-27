# NUS MSc DFT 申请助手 — 数据与检索后端

FT5007 Capstone。本仓库负责 **RAG 知识库与检索层**：把官方语料清洗、结构化、切片、
向量化存入 Supabase，并提供四层混合检索。

回答用的 LLM 和前端不在本仓库（后续接入）。

---

## 当前状态

| 阶段 | 状态 |
|---|---|
| Step 1 连接 Supabase | ✅ |
| Step 2 补齐 + 清洗源数据 | ✅ |
| Step 3-5 切片 + Embedding → **184 chunk** | ✅ |
| Step 6 四层检索（向量 + BM25 + RRF + Rerank） | ✅ |
| Step 7 评估（50-80 题标注 → Pass@k） | ⬜ 进行中 |
| Step 8+ 接回答 LLM、后端 API | ⬜ |

**知识库现状**（`app.document_chunks` = 184 行）

| 来源 | chunk | 切片类别 |
|---|---|---|
| courses | 72 | A（含技能标签）|
| knowledge_snippets | 39 | A |
| programme_pages | 31 | B |
| course_rules | 13 | A |
| admissions_items | 11 | A |
| application_status_translations | 8 | A |
| career_roles | 6 | C |
| competitor_programs | 4 | A |

---

## 环境配置

```bash
# 1. 建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 装依赖
pip install -r requirements.txt

# 3. 配置 .env（见下）
cp .env.example .env

# 4. 验证连接
python scripts/check_supabase_connection.py
```

### .env 只需三个值

```bash
DATABASE_URL=postgresql://...     # Supabase Dashboard > Connect > 连接串
OPENAI_API_KEY=sk-...             # Embedding 用（platform.openai.com，充 $5 够用很久）
COHERE_API_KEY=...                # Rerank 用（dashboard.cohere.com，Trial key 免费）
```

`.env.example` 里其余变量（`SUPABASE_URL` / `SUPABASE_ANON_KEY` /
`SUPABASE_SERVICE_ROLE_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_DIM`）**当前不需要**：
后端直接用 `DATABASE_URL` 连库，模型名写死在脚本里。前面几个是将来前端接入时才用。

> ⚠️ 切勿把 `DATABASE_URL` 或 `SERVICE_ROLE_KEY` 放进前端代码。前端应调后端 API。
> `.env` 已在 `.gitignore` 中。

---

## 脚本

### 检索（Step 6）

```bash
# 四层检索：向量 + BM25 + RRF + Rerank
python scripts/retrieval.py "学费多少钱?"

# 消融对比：并排看只用向量 / 加BM25+RRF / 再加Rerank 的差别
python scripts/retrieval.py "NUS和NTU比怎么样?" --compare

# 指定层数（Step 7 消融用）
python scripts/retrieval.py "..." --mode vector   # 只用①，基线
python scripts/retrieval.py "..." --mode hybrid   # ①②③
python scripts/retrieval.py "..." --mode full     # ①②③④（默认）
```

### 切片（Step 3-5）

三类数据三种切法，都写进同一张 `document_chunks`（upsert，重跑不会重复）：

```bash
# A 类：6 张原子表，1 行 = 1 chunk（147）
python scripts/chunk_atomicA类.py --dry-run       # 先看切出什么，不写库
python scripts/chunk_atomicA类.py --only courses  # 单表调试
python scripts/chunk_atomicA类.py

# B 类：5 页正文按 ##### 标题切（31）
python scripts/chunk_pageB类.py --dry-run
python scripts/chunk_pageB类.py --only page_06
python scripts/chunk_pageB类.py

# C 类：career_roles 按角色聚合（6）
python scripts/chunk_relationalC类.py --dry-run
python scripts/chunk_relationalC类.py
```

### 检查与测试

```bash
python scripts/check_supabase_connection.py   # 连接 / 行数 / RLS 体检
python scripts/test_search.py                 # 10 题纯向量检索抽查（中英文）
```

---

## 文档

| 文件 | 内容 |
|---|---|
| `docs/RAG_PIPELINE_PLAN.md` | **总方案**：技术选型、整体流程、执行进度 |
| `docs/chunk具体说明.md` | **切片细节**：A/B/C 三类各怎么切、为什么 |
| `docs/BM25+RRF+Rerank具体说明.md` | **检索层细节**：四层各在干什么、为什么这么选 |

---

## 关键设计决策

- **Embedding 用 OpenAI `text-embedding-3-small`（1536维）**，不用本地 BGE-m3 —— 开发机
  只有 8GB 内存跑不动；API 成本可忽略（全量 embedding < ¥0.05）。
- **BM25 用 `rank_bm25` 内存版**，不用 Elasticsearch —— 语料仅 184 chunk，起搜索引擎
  集群是杀鸡用牛刀，且 8GB 内存扛不住 JVM。
- **context 前缀用字段模板生成**，不调 LLM（Anthropic Contextual Retrieval 的方案 A）——
  数据规整，模板足够且零成本。方案 B（LLM 生成）留作后续消融实验。
- **技能标签嵌入中文别名** —— 语料是英文但用户用中文提问，在英文 chunk 里埋中文锚点
  提升跨语言召回。实测有效（中文问"哪些课教机器学习"能命中 CS5339/FT5005）。
- **切片数据源是实时数据库，不是 CSV 快照** —— Supabase 导出 CSV 只导前 100 行且不同步删改。
- **官方数据冲突显式标记** —— 招生页"最低 GMAT 650"与 FAQ"无最低线/一般 700"矛盾，
  两个 chunk 打同一 `conflict_group`，FAQ 那条 `authoritative=true`；**不修改官方原文**。

---

## RLS

内部表（不给 anon，只走后端）：
`document_chunks` / `knowledge_snippets` / `source_documents` / `course_corrections_log` /
`import_runs` / `course_rules`

公开可读表：
`admissions_items` / `application_status_translations` / `career_role_modules` /
`career_roles` / `competitor_programs` / `courses` / `module_skills` / `programme_pages` / `skills`

`scripts/check_supabase_connection.py` 会校验这个状态。
