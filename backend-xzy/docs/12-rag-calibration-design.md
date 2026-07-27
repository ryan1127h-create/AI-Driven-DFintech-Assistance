# 设计 — RAG 知识检索 + 阈值校准(研究方向 A)

> **状态**:W4 设计定稿候选 · 待 review
> **来源**:[`11-research-roadmap.md`](11-research-roadmap.md) §3(方向 A)
> **目标读者**:#4–#7 负责人 + 后续接手交付学校的运维
> **配套契约**:RAG 接口见 [`02-interface-contracts.md`](02-interface-contracts.md) §3(本设计是其**离线本地替身**,不改动对外契约)。

---

## 1. 背景与目标

当前 `common/confidence.py` 是一个"空门控":有完整的置信度三级决策逻辑(answer / clarify / escalate),但**没有真实知识库**,无 RAG 分数时只用 lexical 兜底;三个阈值 `0.60 / 0.72 / 0.80` 是经验值,未经校准;`answer_type`(official/advisory/recommendation)在 supervisor 里按 intent 硬编码。

本设计把它升级为**可检索、可校准、provider 可替换**的系统:

1. 建本地 curated 知识库 + 可插拔 `Retriever`,无外部 RAG 时由它供给 chunks。
2. 主检索后端用 **embedding 语义检索**(OpenAI 兼容,默认 DeepSeek),无 key/失败时**降级 BM25**。
3. 用标注查询集**校准阈值**,把经验值替换为数据驱动值,并产出校准曲线作为研究证据。
4. **provider 可换**:交付学校换模型时,改配置(OpenAI 兼容)或加一个适配器(非兼容)+ 重跑校准即可,上层规则引擎/agent/契约不动。

### 非目标(YAGNI)
- 不引入向量数据库;知识库是小型 curated 语料,内存索引足够。
- 不预先实现多个 provider 适配器;只把接口和扩展点讲清。
- 不改动对外 RAG 契约(§3);RAG 队友接入后,其分数仍**优先**于本地检索。

---

## 2. 架构总览

```
                       slots.user_query (无外部 rag_chunks 时)
                                  │
                                  ▼
                    ┌────────────────────────┐
                    │  get_retriever() 工厂    │  按配置选后端 + 失败降级
                    └───────────┬────────────┘
              ┌─────────────────┼─────────────────────┐
              ▼                 ▼                     ▼
   EmbeddingRetriever     BM25Retriever        (未来)学校自有适配器
   (主, 配置驱动)          (离线降级)            实现同一 Retriever 接口
        │                      │
        └──────────┬───────────┘
                   ▼ list[RetrievalChunk] (text, source_id, score)
          common.confidence.decide(...)   ← 既有三级决策, 不改
                   │
                   ▼
        AgentResponse (answer / need_clarification / escalated)

  eval/calibrate.py  ── 读标注查询 → 扫阈值 → 算决策质量 → 最优阈值 + 曲线 (provider 无关)
```

两个可独立理解/测试的单元:**单元 1 = 检索(`common/retriever.py` + 知识库)**;**单元 2 = 校准(`eval/calibrate.py` + 标注查询集)**。单元 2 依赖单元 1 产出分数。

---

## 3. 单元 1:检索

### 3.1 知识库 `data/knowledge/*.jsonl`

每行一个 chunk:

```jsonc
{
  "id": "adm_english_proof",
  "namespace": "admissions",        // admissions | curriculum | faq
  "text": "English proficiency proof (TOEFL/IELTS) is required if your previous degree was not taught mainly in English.",
  "source_id": "admissions_rules#english_proficiency",
  "source_type": "official"         // official | advisory
}
```

- 内容**从项目现有真实数据整理**:`admissions_rules.json` 的条款 → `admissions` 命名空间;`module_catalog.json` 的课程标题/描述 → `curriculum`;另手写 5–10 条常见招生 FAQ → `faq`。
- 每条带 `source_id`(透传到响应 `sources`)与 `source_type`(驱动 `answer_type`)。
- 文件按 namespace 分:`admissions.jsonl` / `curriculum.jsonl` / `faq.jsonl`。

### 3.2 `Retriever` 接口

```python
class Retriever(Protocol):
    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]: ...
```

复用 `confidence.RetrievalChunk(text, source_id, score)`。`namespace=None` 表示跨全部命名空间检索。

### 3.3 `BM25Retriever`(离线降级)

- 纯 Python BM25(stdlib),从知识库构建词项索引;中英文用 `confidence._TOKEN_RE` 同款分词(英文词 + 单字中文)保持一致。
- `score` 为 **IDF 加权的查询覆盖度**,直接落在 `[0,1]`——计算每个查询词在命中 chunk 中的 IDF 权重之和,再除以查询词总 IDF 权重,**不做 min-max 归一化**。因此对当前查询的最大可能分数不影响分母:只匹配停用词的离题查询得分低,保持门控有意义。与 decide() 的阈值语义对齐。
- 完全离线、确定性。

### 3.4 `EmbeddingRetriever`(主,配置驱动)

- **配置**:复用 `common/config.py` 的 key + base_url;新增 `get_embedding_model()`(env `DEEPSEEK_EMBEDDING_MODEL` > 本地文件 > 默认 `deepseek-embedding`)。命名保持中性,文档注明"embedding provider",交付学校换模型时只改这组配置。
- **向量缓存** `data/knowledge/_embeddings.json`:
  ```jsonc
  { "model": "deepseek-embedding", "dim": 1024,
    "vectors": { "adm_english_proof": [0.01, ...], ... } }
  ```
  - 首次或**指纹(model/dim)不匹配**时,对全部 chunk 调用 embedding API 重建缓存。**绝不混用不同模型的向量。**
  - 之后检索不再重算 chunk 向量(省钱、可复现)。
- **检索**:embed 一次 query → 对缓存向量算 cosine → namespace 过滤 → top_k;`score` = cosine(已在 `[-1,1]`,clip 到 `[0,1]`)。
- **失败处理**:无 key、API 报错、端点不存在 → 抛出受控异常,由工厂降级 BM25(对齐 `llm.available()` 的 fail-safe 模式)。

### 3.5 工厂 `get_retriever()`

```
if config.is_configured() and embedding 可用:  EmbeddingRetriever
else:                                          BM25Retriever
运行期 embedding 调用失败 → 本次降级 BM25
```

### 3.6 接入 `supervisor._maybe_apply_confidence_gate`

- 现状:`slots` 同时无 `user_query` 和 `rag_chunks` → 返回 None(跑确定性 agent,行为不变)。
- 现状:有外部 `rag_chunks` → 用其分数 decide(**保持优先**)。
- **新增**:有 `user_query` 但无外部 `rag_chunks` → 用 `get_retriever().retrieve(query, namespace)` 本地补 chunks,再 decide。
- **answer_type 来源驱动**:命中 top chunk 的 `source_type=official` → `answer_type="official"`,否则 `advisory`;替代当前纯 intent 硬编码(intent 仍作为 high_risk 的输入之一)。
- 不破坏现有 `test_supervisor_routing_confidence`:仅在"有 query 无 chunks"分支引入本地检索,其余路径不变。

---

## 4. 单元 2:阈值校准

### 4.1 标注查询集 `eval/cases/retrieval_queries.json`

```jsonc
[
  { "query": "我考了雅思,这个能满足语言要求吗?", "namespace": "admissions",
    "gold_action": "answer" },
  { "query": "错过截止日期还能补交吗?", "namespace": "admissions",
    "gold_action": "escalate" },     // 政策/例外 → 应转人工
  { "query": "区块链相关的课有哪些?", "namespace": "curriculum",
    "gold_action": "answer" },
  { "query": "天气怎么样", "namespace": null,
    "gold_action": "escalate" }      // 无关 → 低置信转人工
]
```

`gold_action ∈ {answer, clarify, escalate}`,覆盖四类:高置信命中、模糊(应追问)、无关(低置信转人工)、政策/例外(应转人工)。

### 4.2 `eval/calibrate.py`

- 对候选阈值做**网格扫描**(`low_threshold` × `clarification_threshold`,`strict` 默认联动)。
- 每组阈值:对每条标注查询跑 `get_retriever().retrieve` + `confidence.decide`(传入该组阈值)→ 得 action → 与 `gold_action` 比。
- 指标:整体决策准确率 + 每类(answer/clarify/escalate)F1(复用 `eval/metrics.py` 的 `set_prf` 思路,按类聚合)。
- 输出:最优阈值组合 + 全网格表(human + `--json`),作为校准曲线数据。
- 入口:`python -m eval.calibrate [--json]`。
- **实测结果(BM25 后端)**:最优 `low=0.15 / clarification=0.30 / strict=0.55`,准确率 1.0(n=13);标注集 answer 类得分 0.71–1.00、escalate 类 0.09–0.18,干净可分。
- **provider 无关**:用当前 `get_retriever()`,所以 BM25 与 embedding 各跑一次即得两套校准结果(报告里做 BM25 vs Embedding 对比)。
- 产出落地:把最优阈值写入 **`data/thresholds.json`**,`confidence.py` 启动时读取(缺省回退到内置常量)。选数据文件而非硬编码常量,贴合项目"数据与逻辑分离、可被 admin 录入工具维护"的既有精神,且校准结果本就是数据产物。

### 4.3 BM25 vs embedding 实测对比(已落地)

接入真实 embedding 后端(Ollama `nomic-embed-text`,768 维,本地离线)重跑校准,与 BM25 同标注集(n=13)对比:

| 后端 | answer 类得分 | escalate 类得分 | 最优阈值 | 准确率 |
|------|--------------|-----------------|----------|--------|
| **BM25**(IDF 覆盖) | 0.71–1.00 | 0.09–0.18 | low=0.20 / clar=0.35 / strict=0.65 | **1.000** |
| **embedding**(cosine) | 0.64–0.87 | 0.41–0.69 | low=0.35 / clar=0.50 / strict=0.70 | **0.923** |

**反直觉发现**:embedding 在本场景**略差**。cosine 空间密集,"政策/例外"类查询("能否过期补交 / 申诉 / 例外" 0.54–0.69)因**语义上确实与招生相关**而得高分,与 answer 类(最低 0.643)重叠,无法用纯阈值干净隔离(误判 1 例);BM25 因这些查询**用词不在知识库**反而低分、干净可分。

**启示**:embedding 召回更强,但"语义相关 ≠ 应自动回答"——政策/例外类应由 `_HIGH_RISK_KEYWORDS` 规则兜底转人工,而非相似度阈值。这正是项目"规则裁决 + 检索"混合架构的价值。

### 4.4 按后端两套阈值(已落地)

不同后端分数分布不同,单套阈值会不安全(如用 BM25 的 `strict=0.55` 评 embedding,会把政策类 0.69 误判 answer、漏转人工)。因此:

- `data/thresholds.json` **按后端分节**:`{"bm25": {...}, "embedding": {...}}`(兼容旧扁平结构)。
- `confidence._load_thresholds(backend)` 读对应节;`decide(..., backend=)` 选用。
- `supervisor._maybe_apply_confidence_gate` 按当前 `get_retriever()` 的类型(`EmbeddingRetriever` → `embedding`,否则 `bm25`)传 `backend`。
- 效果:Ollama 在 → 走 embedding 阈值;关了降级 BM25 → 走 BM25 阈值,**两种情形都安全**。换模型只需重跑 `eval.calibrate` 覆盖对应节。

### 4.5 确定性保证

- 校准/检索逻辑测试用**缓存的固定向量**(纳入 fixture)或 BM25 模式 → 离线、确定。
- 真实 embedding API 调用 → 需 key 实测,测试用 `skip if not config.is_configured()` 标记(对齐 `student/extract` 的实测处理)。
- conftest 隔离凭据,故测试套件**始终离线走 BM25**,不依赖 Ollama。

---

## 5. 测试策略(TDD)

| 测试文件 | 覆盖 |
|---|---|
| `tests/test_retriever.py` | BM25 排序/打分、namespace 过滤、空查询;工厂在无 key 时降级 BM25;缓存指纹不匹配触发重建(用桩 embedder);RetrievalChunk 透传 source_id |
| `tests/test_calibrate.py` | 小标注集网格扫描产出最优阈值;退化情形(全 answer / 全 escalate);指标计算正确 |
| 现有 `tests/` | 全部仍绿(158),尤其 `test_supervisor_routing_confidence` 不回归 |
| 真实 embedding | `skip if not configured`;有 key 时验证 embed 维度、缓存写入、cosine 排序 |

全程纳入 `python -m pytest tests/`;离线默认走 BM25/桩,不联网。

---

## 6. 分阶段实现

1. **阶段 1(检索骨架,离线)**:`Retriever` 接口 + `BM25Retriever` + 知识库三个 jsonl + 工厂 + 接入 supervisor + 测试。可独立交付(本地检索替身)。
2. **阶段 2(embedding 后端)**:`EmbeddingRetriever` + 向量缓存(指纹失效)+ `config.get_embedding_model()` + 工厂降级 + 真实/桩测试。
3. **阶段 3(校准)**:标注查询集 + `eval/calibrate.py` + 产出最优阈值写入 `data/thresholds.json` + `confidence.py` 读取改造(缺省回退内置常量)+ 测试。

---

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| DeepSeek 可能不开放 embedding 端点 | OpenAI 兼容 + base_url 可配 → 改配置指向任意兼容服务;失败自动降级 BM25,不阻断 |
| 交付学校换模型导致旧向量失效 | 缓存带 model/dim 指纹,不匹配自动全量重算;换模型后重跑 `eval.calibrate` 得新阈值 |
| embedding 分数分布与 BM25 不同,旧阈值不适用 | 正是校准要解决的;两后端各自校准,阈值不可跨后端复用 |
| 标注查询集小、主观 | 覆盖四类典型场景;校准集与留出集分离,报告留出集指标;后续可多人标注扩充 |
| 联网/成本/不可复现 | chunk 向量一次性缓存复用;测试默认离线(BM25/桩);真实调用仅在配置 key 时 |
| live embedding 冒烟测试在端点不可用 / key 无效时污染 CI | 已实现:端点不可达或 key 无效时测试 **skip 而非 fail**(`skip if not config.is_configured()`),保证套件不被无效凭据污染 |

---

## 8. 交付学校时的"换模型"操作(运维视角)

1. 配置新 embedding 服务:设 `DEEPSEEK_BASE_URL` / `DEEPSEEK_EMBEDDING_MODEL` / `DEEPSEEK_API_KEY`(OpenAI 兼容);若非兼容,新增一个实现 `Retriever` 接口的适配器。
2. 删除或忽略旧 `_embeddings.json`(指纹不匹配会自动重建)。
3. 跑 `python -m eval.calibrate` 得到适配新模型的阈值并写回。
4. 跑 `python -m pytest tests/` 确认全绿。

上层规则引擎、agent、对外契约**全程不动**。
</content>
