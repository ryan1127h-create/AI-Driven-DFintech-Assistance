"""
Rebuilds the knowledge base's web-sourced retrieval chunks from the live
official MSc DFT pages: the programme pages (one chunk per section, long
sections split) and the FAQ page (one chunk per question). The chunks
built from the structured tables (courses, course_rules, tags_definition,
admissions_items, application_status_translations) are not touched.

    python scripts/knowledge/rebuild_web_chunks.py           # dry run: crawl, build, write the review
    python scripts/knowledge/rebuild_web_chunks.py --apply   # also embed and replace the chunks

Run from backend/. The dry run writes rebuild_review.md and snapshot.json
next to this script and changes nothing. --apply, in one transaction,
stores each page in knowledge.programme_pages (added if new), deletes the old
web chunks (source_table programme_pages, plus any left from the retired
knowledge_snippets) and inserts the new ones with fresh embeddings, then
clears the cached retrievals. Restart the backend afterwards: the chunks
and the BM25 index are cached in process.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tiktoken

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))  # backend/, for app.*

import web_pages  # noqa: E402

PROGRAMME = "the NUS MSc Digital Financial Technology (MSc DFinTech)"
EMBED_MODEL = "text-embedding-3-small"  # must match the query-time model
MAX_TOKENS = 450                         # a longer section is split at paragraph breaks

_MDFT = "https://www.comp.nus.edu.sg/programmes/pg/mdft/"
# The official pages the knowledge base keeps (knowledge.programme_pages),
# in chunking order: a section that appears word for word on two pages is
# kept on the first, so the specific pages come before the overview, which
# repeats the structure page. `topic` is the retrieval bucket the QA tools
# boost; the FAQ page is chunked per question instead of per section.
PAGES = [
    {"page_id": "page_11", "page_index": 11, "label": "Programme Structure", "url": _MDFT + "structure/",
     "domain": "programme_structure", "risk_level": "low", "topic": "academic"},
    {"page_id": "page_03", "page_index": 3, "label": "Capstone Project", "url": _MDFT + "capstone/",
     "domain": "capstone", "risk_level": "medium", "topic": "academic"},
    {"page_id": "page_04", "page_index": 4, "label": "Admission Requirements", "url": _MDFT + "admissions/",
     "domain": "admissions", "risk_level": "high", "topic": "admissions"},
    {"page_id": "page_05", "page_index": 5, "label": "Application Information", "url": _MDFT + "application/",
     "domain": "application", "risk_level": "high", "topic": "admissions"},
    {"page_id": "page_06", "page_index": 6, "label": "Fees and Scholarships", "url": _MDFT + "scholarships/",
     "domain": "fees_scholarships", "risk_level": "high", "topic": "financial"},
    {"page_id": "page_07", "page_index": 7, "label": "FAQ", "url": _MDFT + "faq/",
     "domain": "faq", "risk_level": "medium", "topic": "faq"},
    {"page_id": "page_02", "page_index": 2, "label": "Master of Science in Digital FinTech", "url": _MDFT,
     "domain": "programme_overview", "risk_level": "low", "topic": "academic"},
]
FAQ_PAGE = "page_07"
# Sections left out: marketing copy with no programme facts. (The page's
# PIAC member carousel also lands in this section, without employers.)
SKIP_SECTIONS = {("page_02", "Alumni Testimonial")}
# Headings that start a section: the page title (h1) and the site's section
# headings (h4). Others (names and roles in lists, sub-labels) stay inside.
_SECTION_HEADING = re.compile(r"^(#|####) (.+)$")
FAQ_SECTION_TOPIC = {
    "Admission Criteria": "admissions",
    "Admission": "admissions",
    "Application Process": "admissions",
    "Fees Matters": "financial",
    "Others": "faq",
}
# FAQ questions about careers, wherever the page files them.
FAQ_CAREER_WORDS = ("career", "industry role")

# The page states GMAT/GRE minimums; the FAQ says no score is mandatory and
# governs (the programme's own answer to "is there a cut-off").
CONFLICTS = {
    ("page_04", "Test Scores"): ("test_score_requirement", False),
    ("faq", "cut-off"): ("test_score_requirement", True),
}

_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_key: str
    source_id: str
    content: str
    context: str
    metadata: dict
    answer_type: str = "official"
    authoritative: bool = True
    conflict_group: str | None = None
    source_table: str = "programme_pages"
    token_count: int = field(default=0)

    def __post_init__(self) -> None:
        self.token_count = len(_ENC.encode(f"{self.context}\n{self.content}"))


# ── crawl ─────────────────────────────────────────────────────────────────

def crawl(pages: list[dict]) -> dict:
    snapshot = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pages": {}}
    for page in pages:
        content = web_pages.entry_content(web_pages.fetch(page["url"]))
        markdown = web_pages.to_markdown(content)
        # Drop anything above the page title (a breadcrumb trail).
        if not markdown.startswith("# ") and "\n# " in markdown:
            markdown = markdown[markdown.index("\n# ") + 1:]
        title = re.match(r"^# (.+)$", markdown, flags=re.M)
        entry = {**page, "title": title.group(1) if title else page["label"], "markdown": markdown}
        if page["page_id"] == FAQ_PAGE:
            entry["faq"] = [asdict(item) for item in web_pages.faq_items(content)]
        snapshot["pages"][page["page_id"]] = entry
        print(f"fetched {page['page_id']} {page['label']}: {len(markdown)} chars")
    return snapshot


# ── chunking ──────────────────────────────────────────────────────────────

def _sections(markdown: str) -> list[tuple[str, str]]:
    """(title, text) per heading; the text keeps its heading line. A heading
    with nothing under it before the next heading (e.g. a group title) is
    carried into the next section's text."""
    sections: list[tuple[str, list[str]]] = []
    for block in markdown.split("\n\n"):
        heading = _SECTION_HEADING.match(block)
        if heading or not sections:
            sections.append((heading.group(2).strip() if heading else "", [block]))
        else:
            sections[-1][1].append(block)
    out: list[tuple[str, str]] = []
    carried: list[str] = []
    for title, blocks in sections:
        if len(blocks) == 1 and blocks[0].startswith("#"):
            carried.append(blocks[0])
            continue
        out.append((title, "\n\n".join([*carried, *blocks])))
        carried = []
    return out


def _table_parts(block: str) -> list[str]:
    """A Markdown table too long for one chunk, cut into row groups that
    each repeat the header."""
    lines = block.split("\n")
    header, rows = lines[:2], lines[2:]
    parts, current = [], []
    for row in rows:
        if current and len(_ENC.encode("\n".join([*header, *current, row]))) > MAX_TOKENS:
            parts.append("\n".join([*header, *current]))
            current = []
        current.append(row)
    if current:
        parts.append("\n".join([*header, *current]))
    return parts


def _split(text: str) -> list[str]:
    if len(_ENC.encode(text)) <= MAX_TOKENS:
        return [text]
    blocks = []
    for block in text.split("\n\n"):
        is_table = block.startswith("| ") and "\n| ---" in block
        blocks += _table_parts(block) if is_table and len(_ENC.encode(block)) > MAX_TOKENS else [block]
    parts, current = [], []
    for block in blocks:
        candidate = "\n\n".join([*current, block])
        if current and len(_ENC.encode(candidate)) > MAX_TOKENS:
            parts.append("\n\n".join(current))
            current = [block]
        else:
            current.append(block)
    if current:
        parts.append("\n\n".join(current))
    return parts


def _conflict(key: tuple[str, str]) -> tuple[str | None, bool]:
    return CONFLICTS.get(key, (None, True))


def _body(text: str) -> str:
    """A section's text without its heading lines, for comparing sections."""
    return re.sub(r"^#+ .*$", "", text, flags=re.M).strip()


def page_chunks(page: dict, seen_bodies: set[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for title, text in _sections(page["markdown"]):
        body = _body(text)
        if not body or body in seen_bodies:
            continue  # a heading with no text under it, or a section another page already has
        seen_bodies.add(body)
        title = title or page["label"]
        if (page["page_id"], title) in SKIP_SECTIONS:
            continue
        group, authoritative = _conflict((page["page_id"], title))
        for part in _split(text):
            chunks.append(Chunk(
                chunk_key=f"page:{page['page_id']}:{len(chunks)}",
                source_id=page["page_id"],
                content=part,
                context=(f'This is from the "{title}" section of the {page["label"]} page of {PROGRAMME}. '
                         f"Useful for questions about {title}."),
                metadata={"page_id": page["page_id"], "page_label": page["label"], "section_title": title,
                          "source_url": page["url"], "risk_level": page["risk_level"],
                          "topic": page["topic"]},
                conflict_group=group, authoritative=authoritative,
            ))
    return chunks


def _slug(question: str) -> str:
    stop = {"the", "a", "an", "i", "is", "are", "my", "to", "for", "of", "in", "do", "does", "can", "what",
            "how", "there", "any", "be", "msc", "dfintech", "programme", "program", "this", "you", "am", "on"}
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in stop]
    return "_".join(words[:5]) or "question"


def faq_chunks(page: dict) -> list[Chunk]:
    chunks, seen = [], set()
    for item in page["faq"]:
        question = item["question"]
        topic = FAQ_SECTION_TOPIC.get(item["section"], "faq")
        if any(w in question.lower() for w in FAQ_CAREER_WORDS):
            topic = "career"
        slug = _slug(question)
        while slug in seen:
            slug += "_2"
        seen.add(slug)
        group, authoritative = _conflict(("faq", "cut-off")) if "cut-off" in question.lower() else (None, True)
        chunks.append(Chunk(
            chunk_key=f"faq:{slug}",
            source_id=f"{FAQ_PAGE}#{slug}",
            content=f"Q: {question}\nA: {item['answer']}",
            context=f"Official FAQ answer ({item['section']}) from the {PROGRAMME} programme website.",
            metadata={"page_id": FAQ_PAGE, "page_label": page["label"], "section_title": item["section"],
                      "source_url": page["url"], "risk_level": page["risk_level"], "topic": topic},
            conflict_group=group, authoritative=authoritative,
        ))
    return chunks


def build(snapshot: dict) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen_bodies: set[str] = set()
    for page_id, page in snapshot["pages"].items():  # in PAGES order
        chunks += faq_chunks(page) if page_id == FAQ_PAGE else page_chunks(page, seen_bodies)
    return chunks


# ── review ────────────────────────────────────────────────────────────────

def old_web_chunks() -> list[dict]:
    from app.adapters.knowledge_db_adapter import knowledge_db
    return knowledge_db._query(
        """select chunk_key, source_table, content from knowledge.document_chunks
            where source_table in ('programme_pages', 'knowledge_snippets') order by id""")


_MONEY_DATE = re.compile(
    r"S\$\s?[\d,]+(?:\.\d+)?|\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December) \d{4}\b|\bAY\d{4}/\d{4}\b|\b(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December) \d{4}\b")


def review(chunks: list[Chunk], old: list[dict], snapshot: dict) -> str:
    old_tokens = set(_MONEY_DATE.findall("\n".join(o["content"] for o in old)))
    new_tokens = set(_MONEY_DATE.findall("\n".join(c.content for c in chunks)))
    by_source: dict[str, int] = {}
    for o in old:
        by_source[o["source_table"]] = by_source.get(o["source_table"], 0) + 1
    lines = [
        "# 知识库网页片段重建：核对文档",
        "",
        f"抓取时间 {snapshot['fetched_at']}。由 rebuild_web_chunks.py 生成（试跑，库未改动）。",
        "",
        "## 数量",
        "",
        f"- 旧网页片段 {len(old)} 条：" + "，".join(f"{k} {v}" for k, v in by_source.items()),
        f"- 新片段 {len(chunks)} 条：页面分段 {sum(c.chunk_key.startswith('page:') for c in chunks)}，"
        f"FAQ 问答 {sum(c.chunk_key.startswith('faq:') for c in chunks)}",
        "- 结构化表生成的片段（课程、课程规则、岗位、申请材料、申请状态）不动。",
        "",
        "## 金额和日期的变化",
        "",
        "只出现在旧片段里的（新页面上已经没有）：",
        "",
        *[f"- {t}" for t in sorted(old_tokens - new_tokens)],
        "",
        "只出现在新片段里的：",
        "",
        *[f"- {t}" for t in sorted(new_tokens - old_tokens)],
        "",
        "## 新片段",
        "",
        "| chunk_key | 主题 | 冲突组 | tokens | 开头 |",
        "|---|---|---|---|---|",
    ]
    for c in chunks:
        head = c.content.replace("\n", " ").replace("|", "/")[:90]
        conflict = f"{c.conflict_group} ({'为准' if c.authoritative else '被覆盖'})" if c.conflict_group else ""
        lines.append(f"| `{c.chunk_key}` | {c.metadata['topic']} | {conflict} | {c.token_count} | {head} |")
    lines.append("")
    return "\n".join(lines)


# ── apply ─────────────────────────────────────────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    from app.core.config import settings
    client = OpenAI(api_key=settings.openai_api_key)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), 64):
        response = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + 64])
        vectors += [d.embedding for d in response.data]
    return vectors


def apply(chunks: list[Chunk], snapshot: dict) -> None:
    import psycopg

    from app.core.config import settings
    # Embed what the retriever matches against: the chunk's context and content.
    vectors = embed([f"{c.context}\n{c.content}" for c in chunks])
    fetched_at = snapshot["fetched_at"]
    with psycopg.connect(settings.database_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for page in snapshot["pages"].values():
                cur.execute(
                    """insert into knowledge.programme_pages
                       (page_id, page_index, label, title, url, domain, risk_level, content_markdown, fetched_at)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       on conflict (page_id) do update set
                         page_index = excluded.page_index, label = excluded.label, title = excluded.title,
                         url = excluded.url, domain = excluded.domain, risk_level = excluded.risk_level,
                         content_markdown = excluded.content_markdown, fetched_at = excluded.fetched_at""",
                    (page["page_id"], page["page_index"], page["label"], page["title"], page["url"],
                     page["domain"], page["risk_level"], page["markdown"], fetched_at))
            cur.execute("delete from knowledge.document_chunks "
                        "where source_table in ('programme_pages', 'knowledge_snippets')")
            for c, vec in zip(chunks, vectors):
                cur.execute(
                    """insert into knowledge.document_chunks
                       (chunk_key, source_table, source_id, content, context, embedding, token_count,
                        answer_type, conflict_group, authoritative, metadata)
                       values (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s)""",
                    (c.chunk_key, c.source_table, c.source_id, c.content, c.context,
                     "[" + ",".join(f"{x:.7f}" for x in vec) + "]", c.token_count,
                     c.answer_type, c.conflict_group, c.authoritative, json.dumps(c.metadata, ensure_ascii=False)))
        conn.commit()
    print(f"replaced the web chunks: {len(chunks)} inserted")
    try:
        import redis
        client = redis.from_url(settings.redis_url)
        keys = list(client.scan_iter("rag:retrieve:*"))
        if keys:
            client.delete(*keys)
        print(f"cleared {len(keys)} cached retrievals")
    except Exception as exc:  # the cache is optional; entries expire anyway
        print(f"could not clear the retrieval cache ({exc}); cached entries expire on their own")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="embed and replace the chunks in the database")
    args = parser.parse_args()

    snapshot = crawl(PAGES)
    chunks = build(snapshot)
    keys = [c.chunk_key for c in chunks]
    if len(keys) != len(set(keys)):
        raise SystemExit("duplicate chunk keys")
    (HERE / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERE / "rebuild_review.md").write_text(review(chunks, old_web_chunks(), snapshot), encoding="utf-8")
    print(f"built {len(chunks)} chunks -> rebuild_review.md")
    if args.apply:
        apply(chunks, snapshot)


if __name__ == "__main__":
    main()
