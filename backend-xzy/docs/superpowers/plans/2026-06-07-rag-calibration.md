# RAG 知识检索 + 阈值校准 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 #4–#7 加一个 provider 可换的本地 RAG 检索层 + 数据驱动的阈值校准,把 `common/confidence.py` 的空门控升级为可检索、可校准的系统。

**Architecture:** 可插拔 `Retriever` 接口(BM25 离线降级 + DeepSeek/OpenAI 兼容 embedding 主后端,向量缓存带 model 指纹);`supervisor` 在无外部 RAG 分数时用它本地补 chunks 再走既有 `decide()`;`eval/calibrate.py` 用标注查询集网格扫描产出最优阈值,写入 `data/thresholds.json`。

**Tech Stack:** Python 3.11 / pydantic / openai(已装,OpenAI 兼容 client)/ pytest。纯 stdlib BM25,无新增重依赖。

> **环境说明:** 本仓库非 git 仓库。计划中所有 "Checkpoint" 步骤用 `python -m pytest tests/ -q` 全绿代替 `git commit`。设计依据见 [`docs/12-rag-calibration-design.md`](../../12-rag-calibration-design.md)。

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `common/knowledge.py` | `KnowledgeChunk` + 从 `data/knowledge/*.jsonl` 加载 | Create |
| `common/retriever.py` | `Retriever` 接口 + `BM25Retriever` + `EmbeddingRetriever` + `get_retriever()` | Create |
| `common/embeddings.py` | `embed_texts()` / `embedding_available()`(OpenAI 兼容 client) | Create |
| `common/config.py` | 新增 `get_embedding_model()` | Modify |
| `common/confidence.py` | 阈值改从 `data/thresholds.json` 读取(回退内置常量) | Modify |
| `supervisor.py` | `_maybe_apply_confidence_gate`:无外部 chunks 时本地检索 + answer_type 来源驱动 | Modify |
| `data/knowledge/admissions.jsonl` `curriculum.jsonl` `faq.jsonl` | curated 知识库 | Create |
| `data/thresholds.json` | 校准产物(阈值) | Create(Task 9) |
| `eval/cases/retrieval_queries.json` | 标注查询集 | Create |
| `eval/calibrate.py` | 网格扫描阈值校准 | Create |
| `.gitignore` | 忽略 `data/knowledge/_embeddings.json` | Modify |
| `tests/test_knowledge.py` `test_retriever.py` `test_embeddings.py` `test_calibrate.py` `test_confidence_thresholds.py` | 测试 | Create |

---

# 阶段 1 — 检索骨架(离线)

## Task 1: 知识库加载 `common/knowledge.py` + 数据

**Files:**
- Create: `common/knowledge.py`
- Create: `data/knowledge/admissions.jsonl`, `data/knowledge/curriculum.jsonl`, `data/knowledge/faq.jsonl`
- Test: `tests/test_knowledge.py`

- [ ] **Step 1: 写数据文件 `data/knowledge/admissions.jsonl`**

```jsonl
{"id": "adm_personal_statement", "namespace": "admissions", "text": "Personal statement explains your reasons for applying, preparation for the field, career plans and relevant background.", "source_id": "admissions_rules#personal_statement", "source_type": "official"}
{"id": "adm_cv", "namespace": "admissions", "text": "Curriculum vitae summarises your education, work and internship experience, projects and achievements.", "source_id": "admissions_rules#cv", "source_type": "official"}
{"id": "adm_transcript", "namespace": "admissions", "text": "Official transcripts verify your academic record and must show grades for all courses taken.", "source_id": "admissions_rules#transcript", "source_type": "official"}
{"id": "adm_degree_certificate", "namespace": "admissions", "text": "Official degree certificate or expected graduation letter confirms award or expected completion of your bachelor degree.", "source_id": "admissions_rules#degree_certificate", "source_type": "official"}
{"id": "adm_referee", "namespace": "admissions", "text": "At least two referee reports are required through the online application system.", "source_id": "admissions_rules#referee_reports", "source_type": "official"}
{"id": "adm_fee", "namespace": "admissions", "text": "Only submitted applications with the S$109 application fee paid by the deadline will be processed.", "source_id": "admissions_rules#application_fee", "source_type": "official"}
{"id": "adm_english", "namespace": "admissions", "text": "English proficiency proof such as TOEFL or IELTS is required if your previous university education was not mainly taught in English. 雅思 托福 语言成绩.", "source_id": "admissions_rules#english_proficiency", "source_type": "official"}
{"id": "adm_gre_gmat", "namespace": "admissions", "text": "GRE, GMAT or GATE scores are not mandatory according to current programme notes, but are useful supporting evidence if available.", "source_id": "admissions_rules#standardised_test_scores", "source_type": "advisory"}
```

- [ ] **Step 2: 写数据文件 `data/knowledge/curriculum.jsonl`**

```jsonl
{"id": "cur_ft5001", "namespace": "curriculum", "text": "FT5001 Fintech Innovations: A Strategic Landscape covers the fintech ecosystem and strategy. 金融科技 创新.", "source_id": "module_catalog#FT5001", "source_type": "official"}
{"id": "cur_ft5003", "namespace": "curriculum", "text": "FT5003 Blockchain Innovations covers blockchain, distributed ledgers and digital assets. 区块链 支付.", "source_id": "module_catalog#FT5003", "source_type": "official"}
{"id": "cur_dba5109", "namespace": "curriculum", "text": "DBA5109 Quantitative Risk Management covers quantitative methods for financial risk. 风险 量化.", "source_id": "module_catalog#DBA5109", "source_type": "official"}
{"id": "cur_bt5153", "namespace": "curriculum", "text": "BT5153 Applied Machine Learning for Business Analytics covers ML applied to business and finance data. 机器学习 数据分析.", "source_id": "module_catalog#BT5153", "source_type": "official"}
{"id": "cur_bmf5354", "namespace": "curriculum", "text": "BMF5354 Financial Regulation in a Digital Age covers compliance and regulation for digital finance. 合规 监管.", "source_id": "module_catalog#BMF5354", "source_type": "official"}
{"id": "cur_structure", "namespace": "curriculum", "text": "The MSc Digital Financial Technology requires 40 units of coursework plus a 12-unit capstone, totalling 52 units. 毕业 学分.", "source_id": "module_catalog#structure", "source_type": "official"}
```

- [ ] **Step 3: 写数据文件 `data/knowledge/faq.jsonl`**

```jsonl
{"id": "faq_duration", "namespace": "faq", "text": "The programme can be taken full-time in about one year or part-time over two years.", "source_id": "faq#duration", "source_type": "advisory"}
{"id": "faq_intake", "namespace": "faq", "text": "There is normally one intake per academic year for the programme.", "source_id": "faq#intake", "source_type": "advisory"}
{"id": "faq_work_exp", "namespace": "faq", "text": "Relevant work experience strengthens an application but is not strictly mandatory for all applicants.", "source_id": "faq#work_experience", "source_type": "advisory"}
{"id": "faq_scholarship", "namespace": "faq", "text": "Scholarship and financial aid availability varies by year; check the official programme page for current options.", "source_id": "faq#scholarship", "source_type": "advisory"}
{"id": "faq_online", "namespace": "faq", "text": "Application is submitted online through the NUS Graduate Admission System.", "source_id": "faq#online_application", "source_type": "advisory"}
{"id": "faq_career", "namespace": "faq", "text": "Graduates move into fintech product, quantitative risk, digital banking, payments, compliance and data analytics roles.", "source_id": "faq#careers", "source_type": "advisory"}
```

- [ ] **Step 4: 写失败测试 `tests/test_knowledge.py`**

```python
"""Tests for common.knowledge — loading curated knowledge chunks."""
from __future__ import annotations

from common.knowledge import KnowledgeChunk, load_knowledge


def test_load_all_returns_chunks():
    chunks = load_knowledge()
    assert len(chunks) >= 15
    assert all(isinstance(c, KnowledgeChunk) for c in chunks)


def test_namespaces_present():
    ns = {c.namespace for c in load_knowledge()}
    assert ns == {"admissions", "curriculum", "faq"}


def test_namespace_filter():
    adm = load_knowledge("admissions")
    assert adm
    assert all(c.namespace == "admissions" for c in adm)


def test_chunk_fields_populated():
    c = next(c for c in load_knowledge("admissions") if c.id == "adm_english")
    assert "IELTS" in c.text or "English" in c.text
    assert c.source_id == "admissions_rules#english_proficiency"
    assert c.source_type == "official"
```

- [ ] **Step 5: 运行测试确认失败**

Run: `python -m pytest tests/test_knowledge.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'common.knowledge'`

- [ ] **Step 6: 写实现 `common/knowledge.py`**

```python
"""Curated knowledge base loader (research roadmap A / design doc 12 §3.1).

Chunks live in data/knowledge/*.jsonl, one JSON object per line. The retriever
layer consumes these; nothing here calls an LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    namespace: str  # admissions | curriculum | faq
    text: str
    source_id: str
    source_type: str  # official | advisory


def load_knowledge(namespace: str | None = None) -> list[KnowledgeChunk]:
    """Load curated chunks, optionally filtered to one namespace."""
    chunks: list[KnowledgeChunk] = []
    for path in sorted(_KB_DIR.glob("*.jsonl")):
        if path.name.startswith("_"):
            continue  # skip caches like _embeddings.json analogues
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            chunk = KnowledgeChunk(
                id=d["id"], namespace=d["namespace"], text=d["text"],
                source_id=d["source_id"], source_type=d["source_type"],
            )
            if namespace is None or chunk.namespace == namespace:
                chunks.append(chunk)
    return chunks
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_knowledge.py -q`
Expected: PASS (4 passed)

- [ ] **Step 8: Checkpoint — 全套回归**

Run: `python -m pytest tests/ -q`
Expected: all passed (162)

---

## Task 2: `BM25Retriever`(离线检索后端)

**Files:**
- Create: `common/retriever.py`
- Test: `tests/test_retriever.py`

- [ ] **Step 1: 写失败测试 `tests/test_retriever.py`**

```python
"""Tests for common.retriever — local retrieval backends."""
from __future__ import annotations

from common.confidence import RetrievalChunk
from common.retriever import BM25Retriever


def _bm25() -> BM25Retriever:
    return BM25Retriever()


def test_returns_retrieval_chunks_with_source_id():
    out = _bm25().retrieve("IELTS English language requirement", "admissions", top_k=3)
    assert out and all(isinstance(c, RetrievalChunk) for c in out)
    assert out[0].source_id is not None


def test_english_query_ranks_english_chunk_first():
    out = _bm25().retrieve("Do I need IELTS or TOEFL for English proficiency?",
                           "admissions", top_k=3)
    assert out[0].source_id == "admissions_rules#english_proficiency"


def test_namespace_filter_excludes_other_namespaces():
    out = _bm25().retrieve("blockchain payments", "curriculum", top_k=5)
    assert out
    # every returned chunk must be sourced from the curriculum namespace
    assert all(c.source_id.startswith("module_catalog#") for c in out)


def test_empty_query_returns_empty():
    assert _bm25().retrieve("", "admissions") == []


def test_scores_are_normalised_0_1():
    out = _bm25().retrieve("blockchain", "curriculum", top_k=5)
    assert all(0.0 <= c.score <= 1.0 for c in out)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_retriever.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'common.retriever'`

- [ ] **Step 3: 写实现 `common/retriever.py`(先只 BM25)**

```python
"""Pluggable retrieval backends (design doc 12 §3).

Retriever is the seam for swapping models when delivering to the school: today
a local BM25 backend (offline, deterministic) and an OpenAI-compatible
embedding backend (added in a later task). Both return confidence.RetrievalChunk
so the existing decide() gate is unchanged.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from common.confidence import RetrievalChunk, _tokens
from common.knowledge import KnowledgeChunk, load_knowledge


class Retriever(Protocol):
    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]: ...


def _to_chunk(kc: KnowledgeChunk, score: float) -> RetrievalChunk:
    return RetrievalChunk(text=kc.text, source_id=kc.source_id, score=round(score, 4))


class BM25Retriever:
    """Classic BM25 over the curated knowledge base. Pure stdlib, deterministic."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self._chunks = load_knowledge()
        self._docs = {c.id: _tokens(c.text) for c in self._chunks}
        self._len = {cid: len(toks) for cid, toks in self._docs.items()}
        n = len(self._docs) or 1
        self._avglen = sum(self._len.values()) / n
        # document frequency per term
        df: Counter[str] = Counter()
        for toks in self._docs.values():
            for t in set(toks):
                df[t] += 1
        self._idf = {
            t: math.log(1 + (n - dfi + 0.5) / (dfi + 0.5)) for t, dfi in df.items()
        }

    def _score(self, q_terms: list[str], cid: str) -> float:
        toks = self._docs[cid]
        if not toks:
            return 0.0
        tf = Counter(toks)
        dl = self._len[cid]
        s = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = self._idf.get(t, 0.0)
            num = tf[t] * (self.k1 + 1)
            den = tf[t] + self.k1 * (1 - self.b + self.b * dl / (self._avglen or 1))
            s += idf * num / den
        return s

    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]:
        q_terms = _tokens(query)
        if not q_terms:
            return []
        pool = [c for c in self._chunks
                if namespace is None or c.namespace == namespace]
        scored = [(c, self._score(q_terms, c.id)) for c in pool]
        scored = [(c, s) for c, s in scored if s > 0]
        if not scored:
            return []
        hi = max(s for _, s in scored)
        scored.sort(key=lambda cs: cs[1], reverse=True)
        return [_to_chunk(c, s / hi if hi else 0.0) for c, s in scored[:top_k]]
```

> 注:`common/confidence.py` 已有 `_tokens`(模块级函数)。若它当前是私有但可导入,直接复用;本任务依赖它存在。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_retriever.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Checkpoint — 全套回归**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## Task 3: `get_retriever()` 工厂(无 key → BM25)

**Files:**
- Modify: `common/retriever.py`(追加工厂)
- Test: `tests/test_retriever.py`(追加)

- [ ] **Step 1: 追加失败测试到 `tests/test_retriever.py`**

```python
def test_factory_returns_bm25_when_no_key(monkeypatch):
    from common import config, retriever
    monkeypatch.setattr(config, "is_configured", lambda: False)
    r = retriever.get_retriever()
    assert isinstance(r, retriever.BM25Retriever)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_retriever.py::test_factory_returns_bm25_when_no_key -q`
Expected: FAIL — `AttributeError: module 'common.retriever' has no attribute 'get_retriever'`

- [ ] **Step 3: 追加实现到 `common/retriever.py`**

```python
def get_retriever() -> Retriever:
    """Pick a backend: embedding when configured+usable, else offline BM25.

    EmbeddingRetriever is wired in a later task; until then this returns BM25.
    """
    from common import config

    if config.is_configured():
        try:
            from common.embeddings import embedding_available

            if embedding_available():
                return EmbeddingRetriever()
        except Exception:
            pass  # fail safe -> offline backend
    return BM25Retriever()
```

> 此时 `EmbeddingRetriever` / `common.embeddings` 尚不存在,`config.is_configured()` 在离线测试下为 False,走 BM25 分支;`try/except` 保证半成品状态也安全。Task 6/7 补齐 embedding 后此分支生效。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_retriever.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## Task 4: 接入 `supervisor` — 本地检索补 chunks + answer_type 来源驱动

**Files:**
- Modify: `supervisor.py`(`_maybe_apply_confidence_gate`)
- Test: `tests/test_supervisor_local_retrieval.py`

- [ ] **Step 1: 写失败测试 `tests/test_supervisor_local_retrieval.py`**

```python
"""When a user_query is supplied without external rag_chunks, the supervisor
should retrieve locally and let the gate decide (design doc 12 §3.6)."""
from __future__ import annotations

from common.mock_data import get_profile
import supervisor


def test_relevant_query_passes_gate_and_runs_agent():
    profile = get_profile("1")
    # A clearly on-topic admissions question -> local retrieval finds it ->
    # gate should NOT escalate; the checklist agent runs and returns ok.
    resp = supervisor.route(
        "generate_application_checklist", profile,
        {"user_query": "Do I need IELTS or TOEFL for English proficiency?"},
    )
    assert resp.status == "ok"


def test_offtopic_query_escalates():
    profile = get_profile("1")
    resp = supervisor.route(
        "generate_application_checklist", profile,
        {"user_query": "What is the weather today in Tokyo?"},
    )
    assert resp.status == "escalated"
    assert resp.escalation is not None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_supervisor_local_retrieval.py -q`
Expected: FAIL — off-topic 当前已 escalate(chunks=[]),但 on-topic 当前也会 escalate(无检索 → chunks=[]),故 `test_relevant_query_passes_gate_and_runs_agent` 失败。

- [ ] **Step 3: 修改 `supervisor._maybe_apply_confidence_gate`**

定位现有分支(`supervisor.py` 约 173–197 行)。把"有 query、无 chunks → chunks=[]"替换为本地检索:

```python
    query = slots.get("user_query") or slots.get("query") or slots.get("question")
    chunks = slots.get("rag_chunks") or slots.get("retrieval_chunks")
    if query is None and chunks is None:
        return None
    if query is None:
        query = ""
    if chunks is None:
        # No external RAG chunks: retrieve locally (design doc 12 §3.6).
        from common.retriever import get_retriever

        namespace = slots.get("namespace")
        retrieved = get_retriever().retrieve(str(query), namespace)
        chunks = [
            {"text": c.text, "source_id": c.source_id, "score": c.score}
            for c in retrieved
        ]

    source_agent = _SOURCE_AGENT[intent]
    # answer_type is source-driven: an official top source keeps it official.
    intent_default = "official" if intent in _OFFICIAL_INTENTS else "advisory"
    answer_type = intent_default
    high_risk = bool(slots.get("high_risk")) or intent in _OFFICIAL_INTENTS
    decision = confidence_decide(
        str(query), list(chunks), answer_type=answer_type, high_risk=high_risk,
    )
    return response_from_decision(
        decision, profile=profile, source_agent=source_agent,
        query=str(query),
        suggested_routing=_ROUTING_TEAM.get(source_agent, "programme_office"),
    )
```

> 行为变化仅在"有 query、无外部 chunks"分支:由"必然空检索→escalate"变为"本地检索后再判定"。其余分支(无 query 无 chunks / 有外部 chunks)不变,保证 `test_supervisor_routing_confidence` 不回归。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_supervisor_local_retrieval.py tests/test_supervisor_routing_confidence.py -q`
Expected: PASS(新 2 + 原 7)

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

# 阶段 2 — Embedding 后端

## Task 5: `config.get_embedding_model()` + `common/embeddings.py`

**Files:**
- Modify: `common/config.py`
- Create: `common/embeddings.py`
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: 写失败测试 `tests/test_embeddings.py`**

```python
"""Tests for embedding config + client wrapper (offline-safe)."""
from __future__ import annotations

from common import config, embeddings


def test_default_embedding_model():
    # default when nothing configured
    assert isinstance(config.get_embedding_model(), str)
    assert config.get_embedding_model()  # non-empty


def test_env_overrides_embedding_model(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_EMBEDDING_MODEL", "school-embed-v1")
    assert config.get_embedding_model() == "school-embed-v1"


def test_embedding_available_false_without_key(monkeypatch):
    monkeypatch.setattr(config, "is_configured", lambda: False)
    assert embeddings.embedding_available() is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_embeddings.py -q`
Expected: FAIL — `AttributeError: module 'common.config' has no attribute 'get_embedding_model'`

- [ ] **Step 3: 加 `get_embedding_model()` 到 `common/config.py`**

在 `_DEFAULT_MODEL` 附近加默认常量,并在 `get_model()` 之后加函数:

```python
_DEFAULT_EMBEDDING_MODEL = "deepseek-embedding"
```

```python
def get_embedding_model() -> str:
    return (
        os.getenv("DEEPSEEK_EMBEDDING_MODEL")
        or _read_file().get("embedding_model")
        or _DEFAULT_EMBEDDING_MODEL
    )
```

- [ ] **Step 4: 写实现 `common/embeddings.py`**

```python
"""OpenAI-compatible embedding client (design doc 12 §3.4).

Mirrors common/llm.py: reads credentials via common/config.py, fails safe.
Used only by the embedding retrieval backend; swap providers by changing
DEEPSEEK_BASE_URL / DEEPSEEK_EMBEDDING_MODEL (no code change).
"""
from __future__ import annotations

from . import config


def embedding_available() -> bool:
    return config.is_configured()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one vector per input text. Raises on misconfig/API error so the
    retriever factory can fall back to BM25."""
    if not texts:
        return []
    from openai import OpenAI

    client = OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())
    resp = client.embeddings.create(model=config.get_embedding_model(), input=texts)
    return [d.embedding for d in resp.data]
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_embeddings.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## Task 6: `EmbeddingRetriever` + 向量缓存(指纹失效)

**Files:**
- Modify: `common/retriever.py`(加 `EmbeddingRetriever`)
- Modify: `.gitignore`(忽略缓存)
- Test: `tests/test_retriever.py`(追加,用桩 embedder)

- [ ] **Step 1: 追加失败测试到 `tests/test_retriever.py`**

```python
def test_embedding_retriever_ranks_by_cosine(monkeypatch, tmp_path):
    """With a stub embedder, the chunk closest in vector space ranks first.
    Deterministic: no network, fixed vectors."""
    from common import retriever as R

    # Map specific texts to fixed 2-D vectors; query closest to 'english' chunk.
    def fake_embed(texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "ielts" in tl or "english" in tl:
                out.append([1.0, 0.0])
            elif "blockchain" in tl:
                out.append([0.0, 1.0])
            else:
                out.append([0.5, 0.5])
        return out

    monkeypatch.setattr(R, "_cache_path", lambda: tmp_path / "_emb.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)

    er = R.EmbeddingRetriever()
    out = er.retrieve("english language IELTS requirement", "admissions", top_k=1)
    assert out and out[0].source_id == "admissions_rules#english_proficiency"


def test_embedding_cache_rebuilds_on_model_fingerprint_change(monkeypatch, tmp_path):
    from common import retriever as R

    calls = {"n": 0}

    def fake_embed(texts):
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(R, "_cache_path", lambda: tmp_path / "_emb.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-A")
    R.EmbeddingRetriever()  # builds cache for model-A
    n_after_a = calls["n"]
    # Same model -> reuse cache (no new embed calls for chunks)
    R.EmbeddingRetriever()
    assert calls["n"] == n_after_a
    # Different model -> fingerprint mismatch -> rebuild
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-B")
    R.EmbeddingRetriever()
    assert calls["n"] > n_after_a
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_retriever.py -k embedding -q`
Expected: FAIL — `AttributeError: ... has no attribute 'EmbeddingRetriever'`

- [ ] **Step 3: 追加实现到 `common/retriever.py`**

顶部加 import:

```python
import json
from pathlib import Path

from common import config, embeddings
```

加缓存路径与类:

```python
_KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"


def _cache_path() -> Path:
    return _KB_DIR / "_embeddings.json"


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


class EmbeddingRetriever:
    """OpenAI-compatible embedding retrieval with a fingerprinted vector cache.

    Chunk vectors are embedded once and cached; the cache is rebuilt whenever the
    embedding model fingerprint changes (never mixes vectors across models).
    """

    def __init__(self) -> None:
        self._chunks = load_knowledge()
        self._model = config.get_embedding_model()
        self._vectors = self._load_or_build_cache()

    def _load_or_build_cache(self) -> dict[str, list[float]]:
        path = _cache_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("model") == self._model:
                    return data.get("vectors", {})
            except (json.JSONDecodeError, OSError):
                pass
        vecs = embeddings.embed_texts([c.text for c in self._chunks])
        vectors = {c.id: v for c, v in zip(self._chunks, vecs)}
        dim = len(vecs[0]) if vecs else 0
        try:
            path.write_text(
                json.dumps({"model": self._model, "dim": dim, "vectors": vectors}),
                encoding="utf-8",
            )
        except OSError:
            pass
        return vectors

    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]:
        if not query.strip():
            return []
        qv = embeddings.embed_texts([query])[0]
        pool = [c for c in self._chunks
                if namespace is None or c.namespace == namespace]
        scored = [(c, _cosine(qv, self._vectors[c.id]))
                  for c in pool if c.id in self._vectors]
        scored.sort(key=lambda cs: cs[1], reverse=True)
        return [_to_chunk(c, s) for c, s in scored[:top_k]]
```

- [ ] **Step 4: 加 `.gitignore` 忽略缓存**

在 `.gitignore` 末尾追加:

```
data/knowledge/_embeddings.json
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_retriever.py -q`
Expected: PASS(全部,含 2 个新 embedding 测试)

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## Task 7: 工厂升级 + 真实 embedding 冒烟测试(需 key,自动 skip)

**Files:**
- Test: `tests/test_retriever.py`(追加真实调用 skip 测试)

> `get_retriever()` 在 Task 3 已写成"有 key+embedding 可用 → EmbeddingRetriever",Task 6 已实现 `EmbeddingRetriever`,故工厂分支此刻自动生效,无需改工厂。本任务补一个 key 在场时的冒烟测试。

- [ ] **Step 1: 追加 skip 测试到 `tests/test_retriever.py`**

```python
import pytest
from common import config


@pytest.mark.skipif(not config.is_configured(),
                    reason="needs DeepSeek/embedding key for live call")
def test_live_embedding_retriever_smoke():
    from common.retriever import EmbeddingRetriever

    er = EmbeddingRetriever()
    out = er.retrieve("English language proof", "admissions", top_k=2)
    assert out
    assert all(0.0 <= c.score <= 1.0 for c in out)
```

- [ ] **Step 2: 运行(离线应 skip)**

Run: `python -m pytest tests/test_retriever.py -q`
Expected: PASS,1 skipped(无 key 时)

- [ ] **Step 3: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed(若配了 key,冒烟测试实跑)

---

# 阶段 3 — 阈值校准

## Task 8: 标注查询集 + `eval/calibrate.py`

**Files:**
- Create: `eval/cases/retrieval_queries.json`
- Create: `eval/calibrate.py`
- Test: `tests/test_calibrate.py`

- [ ] **Step 1: 写标注集 `eval/cases/retrieval_queries.json`**

```json
[
  {"query": "Do I need IELTS or TOEFL for English proficiency?", "namespace": "admissions", "gold_action": "answer"},
  {"query": "What documents do I submit for the application?", "namespace": "admissions", "gold_action": "answer"},
  {"query": "Which modules cover blockchain and payments?", "namespace": "curriculum", "gold_action": "answer"},
  {"query": "How many units do I need to graduate?", "namespace": "curriculum", "gold_action": "answer"},
  {"query": "Can I still apply after the deadline has passed?", "namespace": "admissions", "gold_action": "escalate"},
  {"query": "I want to appeal a rejected application decision", "namespace": "admissions", "gold_action": "escalate"},
  {"query": "What is the weather today in Tokyo?", "namespace": null, "gold_action": "escalate"},
  {"query": "tell me a joke about cats", "namespace": null, "gold_action": "escalate"}
]
```

> gold 设计:on-topic 命中 → answer;政策/例外(deadline/appeal,命中 high-risk 关键词)→ escalate;无关 → 低置信 escalate。clarify 类在小集里不强制覆盖(分数分布连续,校准会自然探索中间档)。

- [ ] **Step 2: 写失败测试 `tests/test_calibrate.py`**

```python
"""Tests for eval.calibrate — threshold grid search over labelled queries."""
from __future__ import annotations

from eval.calibrate import evaluate_thresholds, grid_search, load_queries


def test_queries_load():
    qs = load_queries()
    assert len(qs) >= 8
    assert {q["gold_action"] for q in qs} <= {"answer", "clarify", "escalate"}


def test_evaluate_thresholds_returns_accuracy():
    qs = load_queries()
    r = evaluate_thresholds(qs, low=0.60, clarification=0.72, strict=0.80)
    assert 0.0 <= r["accuracy"] <= 1.0
    assert r["n"] == len(qs)


def test_grid_search_picks_best_by_accuracy():
    qs = load_queries()
    best, table = grid_search(qs)
    assert table  # non-empty grid
    assert best in table
    # best must be the max-accuracy cell
    assert best["accuracy"] == max(row["accuracy"] for row in table)
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_calibrate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.calibrate'`

- [ ] **Step 4: 写实现 `eval/calibrate.py`**

```python
"""Threshold calibration for the confidence gate (design doc 12 §4).

Grid-search the decide() thresholds against a labelled query set, score by
decision accuracy, and report the best cell. Provider-agnostic: uses the active
retriever (BM25 offline, embedding when configured), so re-running after a model
swap yields fresh thresholds.

    python -m eval.calibrate            # human-readable
    python -m eval.calibrate --json     # machine-readable
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common.confidence import decide
from common.retriever import get_retriever

_QUERIES = Path(__file__).resolve().parent / "cases" / "retrieval_queries.json"

# Candidate threshold values to scan.
_LOWS = [0.30, 0.40, 0.50, 0.60]
_CLARS = [0.55, 0.65, 0.72, 0.80]
_STRICTS = [0.80, 0.90]


def load_queries() -> list[dict]:
    return json.loads(_QUERIES.read_text(encoding="utf-8"))


def _action_for(query: dict, retriever, low: float, clar: float, strict: float) -> str:
    chunks = retriever.retrieve(query["query"], query.get("namespace"))
    payload = [{"text": c.text, "source_id": c.source_id, "score": c.score}
               for c in chunks]
    # Official-source questions use the stricter rule; mirror supervisor's flag.
    decision = decide(query["query"], payload, answer_type="official",
                      high_risk=False, low_threshold=low,
                      clarification_threshold=clar, strict_threshold=strict)
    return decision.action


def evaluate_thresholds(queries: list[dict], low: float, clarification: float,
                        strict: float) -> dict:
    retriever = get_retriever()
    correct = 0
    for q in queries:
        if _action_for(q, retriever, low, clarification, strict) == q["gold_action"]:
            correct += 1
    n = len(queries)
    return {"low": low, "clarification": clarification, "strict": strict,
            "accuracy": correct / n if n else 0.0, "n": n}


def grid_search(queries: list[dict]) -> tuple[dict, list[dict]]:
    table: list[dict] = []
    for low in _LOWS:
        for clar in _CLARS:
            if clar < low:
                continue  # clarification band must sit above low
            for strict in _STRICTS:
                table.append(evaluate_thresholds(queries, low, clar, strict))
    best = max(table, key=lambda r: r["accuracy"])
    return best, table


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    queries = load_queries()
    best, table = grid_search(queries)
    if "--json" in argv:
        print(json.dumps({"best": best, "grid": table}, ensure_ascii=False, indent=2))
    else:
        print("=== Threshold calibration (active retriever) ===\n")
        for row in sorted(table, key=lambda r: r["accuracy"], reverse=True)[:10]:
            print(f"  acc={row['accuracy']:.3f}  low={row['low']:.2f} "
                  f"clar={row['clarification']:.2f} strict={row['strict']:.2f}")
        print(f"\nBEST: low={best['low']:.2f} clarification={best['clarification']:.2f} "
              f"strict={best['strict']:.2f}  accuracy={best['accuracy']:.3f} "
              f"(n={best['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_calibrate.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: 跑一次校准看真实输出**

Run: `python -m eval.calibrate`
Expected: 打印网格 top-10 + BEST 行(离线 BM25 后端)

- [ ] **Step 7: Checkpoint**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## Task 9: 阈值写回 `data/thresholds.json` + `confidence.py` 读取

**Files:**
- Create: `data/thresholds.json`
- Modify: `common/confidence.py`(读取数据文件,回退常量)
- Test: `tests/test_confidence_thresholds.py`

- [ ] **Step 1: 写失败测试 `tests/test_confidence_thresholds.py`**

```python
"""decide() should read default thresholds from data/thresholds.json when
present, falling back to built-in constants otherwise."""
from __future__ import annotations

from common import confidence


def test_loads_thresholds_from_file_when_present(tmp_path, monkeypatch):
    import json
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps({"low": 0.42, "clarification": 0.55, "strict": 0.88}),
                 encoding="utf-8")
    monkeypatch.setattr(confidence, "_THRESHOLDS_PATH", f)
    confidence._load_thresholds.cache_clear()
    t = confidence._load_thresholds()
    assert t == {"low": 0.42, "clarification": 0.55, "strict": 0.88}


def test_falls_back_to_constants_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(confidence, "_THRESHOLDS_PATH", tmp_path / "nope.json")
    confidence._load_thresholds.cache_clear()
    t = confidence._load_thresholds()
    assert t["low"] == confidence.LOW_CONFIDENCE_THRESHOLD
    assert t["clarification"] == confidence.CLARIFICATION_THRESHOLD
    assert t["strict"] == confidence.STRICT_OFFICIAL_THRESHOLD
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_confidence_thresholds.py -q`
Expected: FAIL — `AttributeError: module 'common.confidence' has no attribute '_load_thresholds'`

- [ ] **Step 3: 改 `common/confidence.py` — 加阈值文件读取**

顶部 import 区加:

```python
from functools import lru_cache
from pathlib import Path
```

在三个常量定义后加:

```python
_THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "data" / "thresholds.json"


@lru_cache(maxsize=1)
def _load_thresholds() -> dict[str, float]:
    """Calibrated thresholds from data/thresholds.json, else built-in defaults."""
    defaults = {
        "low": LOW_CONFIDENCE_THRESHOLD,
        "clarification": CLARIFICATION_THRESHOLD,
        "strict": STRICT_OFFICIAL_THRESHOLD,
    }
    try:
        import json
        data = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        return {k: float(data.get(k, defaults[k])) for k in defaults}
    except (OSError, ValueError):
        return defaults
```

把 `decide()` 的默认参数改为从文件读取。当前签名用模块常量做默认值;改为 `None` 哨兵 + 运行期填充:

```python
def decide(
    query: str,
    chunks: list[Any],
    *,
    answer_type: str = "advisory",
    high_risk: bool = False,
    low_threshold: float | None = None,
    clarification_threshold: float | None = None,
    strict_threshold: float | None = None,
) -> ConfidenceDecision:
    """Decide whether to answer, clarify, or escalate after RAG retrieval."""
    t = _load_thresholds()
    if low_threshold is None:
        low_threshold = t["low"]
    if clarification_threshold is None:
        clarification_threshold = t["clarification"]
    if strict_threshold is None:
        strict_threshold = t["strict"]
    # ... rest of the existing body unchanged ...
```

> 显式传阈值的调用方(如 `eval/calibrate.py`)不受影响;默认调用方自动用校准值。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_confidence_thresholds.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: 生成校准产物并写入 `data/thresholds.json`**

Run: `python -m eval.calibrate --json`
取输出 `best` 的 low/clarification/strict,写入 `data/thresholds.json`:

```json
{"low": 0.40, "clarification": 0.65, "strict": 0.80, "_note": "calibrated by eval.calibrate on BM25 backend; re-run after embedding/model swap"}
```

> 实际数值以本机 `eval.calibrate --json` 的 `best` 为准填入(上面为占位示例,执行时用真实输出覆盖)。

- [ ] **Step 6: Checkpoint — 全套回归(确认阈值变化未破坏既有门控测试)**

Run: `python -m pytest tests/ -q`
Expected: all passed。若 `test_supervisor_routing_confidence` 因新默认阈值变化而失败,核对该测试是否硬编码了旧阈值语义;如是,更新为显式传阈值或对齐校准值(在该步修复并记录原因)。

---

## Task 10: 文档与收尾

**Files:**
- Modify: `README.md`(检索/校准入口一行)
- Modify: `docs/11-research-roadmap.md`(把 A 标记为已落地最小版)

- [ ] **Step 1: README「测试 / 运行」区加两行**

```markdown
## RAG 检索与阈值校准(研究方向 A)
- 本地检索:无外部 RAG 时由 `common/retriever.py` 供给 chunks(BM25 离线 / DeepSeek embedding 主,失败降级)。
- 阈值校准:`python -m eval.calibrate`(产物写 `data/thresholds.json`,换模型后重跑)。详见 [设计文档](docs/12-rag-calibration-design.md)。
```

- [ ] **Step 2: `docs/11-research-roadmap.md` §7 里程碑表把 A 行标 ✅(W4)**

将 A 相关行状态从 ⬜ 改为 ✅,并注明 "检索骨架 + embedding 后端 + 阈值校准已落地"。

- [ ] **Step 3: Checkpoint — 最终全套**

Run: `python -m pytest tests/ -q`
Expected: all passed

---

## 自审记录(spec coverage)

- §3.1 知识库 → Task 1 ✅
- §3.2/3.3 接口 + BM25 → Task 2 ✅
- §3.4 EmbeddingRetriever + 缓存指纹 → Task 6 ✅
- §3.5 工厂降级 → Task 3 + Task 7 ✅
- §3.6 supervisor 接入 + answer_type 来源驱动 → Task 4 ✅
- §4.1 标注查询集 → Task 8 ✅
- §4.2 calibrate 网格扫描 → Task 8 ✅
- §4.2 阈值写回 data/thresholds.json + confidence 读取 → Task 9 ✅
- §5 测试策略(含离线 skip / 桩 embedder)→ Task 5/6/7 ✅
- §3.4 config.get_embedding_model → Task 5 ✅
- 缓存 gitignore → Task 6 ✅
</content>
