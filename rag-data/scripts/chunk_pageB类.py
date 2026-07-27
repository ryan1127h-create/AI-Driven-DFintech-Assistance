"""B-class chunking: long page bodies -> split by heading -> embed -> load.

Reads app.programme_pages (rag_include=true), skips page_07 (FAQ, already in
A-class), and turns each page body into chunks:

  1. split the markdown by its ##### headings into sections
  2. a section <= MAX_TOKENS is one chunk; a longer section is split again at
     paragraph boundaries into ~MAX_TOKENS windows with OVERLAP_TOKENS overlap
  3. each chunk gets a template context prefix (page + programme name) so it
     knows where it belongs -- contextual retrieval, method A
  4. embed (context + content) and upsert into document_chunks (key prefix page:)

    python scripts/chunk_pageB类.py --dry-run       # split + print, no OpenAI/write
    python scripts/chunk_pageB类.py --only page_06   # one page
    python scripts/chunk_pageB类.py                  # embed all + upsert
"""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

APP_SCHEMA = "app"
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 128
PROGRAMME = "NUS MSc Digital Financial Technology (MSc DFinTech)"

MAX_TOKENS = 500       # a section/window up to this many tokens is one chunk
OVERLAP_TOKENS = 50    # overlap between windows when a section is split again

SKIP_PAGES = {"page_07"}  # FAQ already chunked in A-class

CONFLICT_TEST_SCORE = "test_score_requirement"
HEADING_RE = re.compile(r"^(#{2,6})\s+(.+)$", re.M)

# An in-page nav anchor line: "- Application (#application)". Pure navigation.
NAV_ANCHOR_RE = re.compile(r"^-\s+.+\(#[^)]*\)\s*$", re.M)

# Sections to skip entirely because their content is fully covered elsewhere.
# page_05 "Submission of Application" holds the mandatory-documents table, which
# duplicates the 11 admissions_items chunks (A-class) that answer it better.
SKIP_SECTIONS = {
    ("page_05", "submission of application"),
}


def has_real_content(body: str, title: str) -> bool:
    """True if the block has substance beyond its heading and nav anchors.

    Length-agnostic: a short but real line ("minimum allowance is S$1,200")
    counts; a bare title or a list of #anchor links does not.
    """
    text = body
    # drop every heading line (## ... through ###### ...)
    text = HEADING_RE.sub("", text)
    # drop in-page nav anchor lines
    text = NAV_ANCHOR_RE.sub("", text)
    return bool(text.strip())


@dataclass
class Chunk:
    chunk_key: str
    source_table: str
    source_id: str
    content: str
    context: str
    answer_type: str = "official"
    conflict_group: str | None = None
    authoritative: bool = True
    metadata: dict = field(default_factory=dict)

    @property
    def embed_input(self) -> str:
        return f"{self.context}\n{self.content}"


# --- token counting ---------------------------------------------------------

_enc = None


def n_tokens(text: str) -> int:
    global _enc
    if _enc is None:
        import tiktoken
        _enc = tiktoken.get_encoding("cl100k_base")  # matches 3-small
    return len(_enc.encode(text))


# --- splitting --------------------------------------------------------------

@dataclass
class Section:
    title: str          # heading text, "" for any preamble before first heading
    body: str           # full text of the section, heading line included


def split_sections(markdown: str) -> list[Section]:
    """Split a page into sections at markdown headings."""
    matches = list(HEADING_RE.finditer(markdown))
    if not matches:
        return [Section(title="", body=markdown.strip())]

    sections: list[Section] = []
    # any text before the first heading
    if matches[0].start() > 0:
        pre = markdown[: matches[0].start()].strip()
        if pre:
            sections.append(Section(title="", body=pre))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        title = m.group(2).strip()
        # strip inline markdown-link parens from the heading title for readability
        title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
        sections.append(Section(title=title, body=markdown[m.start():end].strip()))
    return sections


def split_long_body(body: str) -> list[str]:
    """Split an over-length section into ~MAX_TOKENS windows at paragraph
    boundaries, carrying OVERLAP_TOKENS of the previous window for continuity."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    windows: list[str] = []
    cur: list[str] = []
    cur_tok = 0

    for para in paras:
        pt = n_tokens(para)
        if cur and cur_tok + pt > MAX_TOKENS:
            windows.append("\n\n".join(cur))
            # start next window with a tail overlap of the previous one
            tail, tail_tok = [], 0
            for p in reversed(cur):
                t = n_tokens(p)
                if tail_tok + t > OVERLAP_TOKENS:
                    break
                tail.insert(0, p)
                tail_tok += t
            cur, cur_tok = list(tail), tail_tok
        cur.append(para)
        cur_tok += pt

    if cur:
        windows.append("\n\n".join(cur))
    return windows


# --- chunk building ---------------------------------------------------------

def build_page_chunks(page: dict) -> list[Chunk]:
    page_id = page["page_id"]
    label = page["label"]
    url = page.get("url") or page.get("final_url") or ""
    risk = page.get("risk_level")
    md = page["content_markdown"] or ""

    chunks: list[Chunk] = []
    idx = 0
    for section in split_sections(md):
        if not section.body.strip():
            continue

        # skip sections fully covered elsewhere (e.g. the documents table that
        # duplicates admissions_items)
        if (page_id, section.title.lower()) in SKIP_SECTIONS:
            continue

        # skip pure-title / pure-navigation blocks: the page title itself lives
        # in every chunk's context, so a heading with no body is just noise
        if not has_real_content(section.body, section.title):
            continue

        bodies = [section.body]
        if n_tokens(section.body) > MAX_TOKENS:
            bodies = split_long_body(section.body)

        for part_no, body in enumerate(bodies):
            where = f'the "{section.title}" section of ' if section.title else ""
            context = (
                f"This is from {where}the {label} page of the {PROGRAMME}. "
                f"Useful for questions about {section.title or label}."
            )

            # GMAT conflict: the Admission Requirements "Test Scores" section
            # states minimum GMAT 650, which the FAQ overrides.
            conflict, authoritative = None, True
            if page_id == "page_04" and section.title.lower().startswith("test scores"):
                conflict, authoritative = CONFLICT_TEST_SCORE, False

            chunks.append(Chunk(
                chunk_key=f"page:{page_id}:{idx}",
                source_table="programme_pages",
                source_id=page_id,
                content=body,
                context=context,
                answer_type="official",
                conflict_group=conflict,
                authoritative=authoritative,
                metadata={
                    "page_id": page_id,
                    "page_label": label,
                    "section_title": section.title or None,
                    "source_url": url,
                    "risk_level": risk,
                    "part": part_no if len(bodies) > 1 else None,
                },
            ))
            idx += 1
    return chunks


# --- embedding + load (same contract as chunk_atomic) -----------------------

def fetch_pages(conn: psycopg.Connection, only: str | None) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select page_id, label, url, final_url, risk_level, content_markdown
            from {APP_SCHEMA}.programme_pages
            where rag_include = true and content_markdown is not null
            order by page_index
        """)
        rows = cur.fetchall()
    rows = [r for r in rows if r["page_id"] not in SKIP_PAGES]
    if only:
        rows = [r for r in rows if r["page_id"] == only]
    return rows


def embed(client, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + EMBED_BATCH])
        vectors.extend(d.embedding for d in resp.data)
    return vectors


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def upsert(conn: psycopg.Connection, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    sql = f"""
        insert into {APP_SCHEMA}.document_chunks
          (chunk_key, source_table, source_id, content, context, embedding,
           token_count, answer_type, conflict_group, authoritative, metadata)
        values
          (%(chunk_key)s, %(source_table)s, %(source_id)s, %(content)s, %(context)s,
           %(embedding)s, %(token_count)s, %(answer_type)s, %(conflict_group)s,
           %(authoritative)s, %(metadata)s)
        on conflict (chunk_key) do update set
           source_table=excluded.source_table, source_id=excluded.source_id,
           content=excluded.content, context=excluded.context,
           embedding=excluded.embedding, token_count=excluded.token_count,
           answer_type=excluded.answer_type, conflict_group=excluded.conflict_group,
           authoritative=excluded.authoritative, metadata=excluded.metadata
    """
    with conn.cursor() as cur:
        for chunk, vec in zip(chunks, vectors):
            cur.execute(sql, {
                "chunk_key": chunk.chunk_key,
                "source_table": chunk.source_table,
                "source_id": chunk.source_id,
                "content": chunk.content,
                "context": chunk.context,
                "embedding": to_pgvector(vec),
                "token_count": n_tokens(chunk.embed_input),
                "answer_type": chunk.answer_type,
                "conflict_group": chunk.conflict_group,
                "authoritative": chunk.authoritative,
                "metadata": Jsonb({k: v for k, v in chunk.metadata.items() if v is not None}),
            })
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="chunk just one page_id, e.g. page_06")
    parser.add_argument("--dry-run", action="store_true",
                        help="split and print chunks; no OpenAI call, no write")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. See .env.example.")

    with psycopg.connect(database_url) as conn:
        pages = fetch_pages(conn, args.only)
        all_chunks: list[Chunk] = []
        for page in pages:
            chunks = build_page_chunks(page)
            all_chunks.extend(chunks)
            print(f"{page['page_id']}  {page['label'][:34]:36} -> {len(chunks):>2} chunks")

        print(f"\nTotal: {len(all_chunks)} chunks from {len(pages)} pages")

        if args.dry_run:
            print("\n--- chunks ---")
            for c in all_chunks:
                tok = n_tokens(c.content)
                flag = f"  conflict={c.conflict_group}" if c.conflict_group else ""
                print(f"\n[{c.chunk_key}] {tok} tok  section={c.metadata.get('section_title')}{flag}")
                print(f"  context: {c.context}")
                print(f"  content: {c.content[:160].replace(chr(10), ' ')}...")
            print("\nDRY RUN: nothing embedded or written.")
            return

        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise SystemExit("OPENAI_API_KEY is missing. See .env.example.")
        from openai import OpenAI
        client = OpenAI(api_key=key)

        print(f"\nEmbedding {len(all_chunks)} chunks with {EMBED_MODEL}...")
        vectors = embed(client, [c.embed_input for c in all_chunks])

        print("Writing to document_chunks...")
        upsert(conn, all_chunks, vectors)

        with conn.cursor() as cur:
            cur.execute(f"select count(*) from {APP_SCHEMA}.document_chunks")
            total = cur.fetchone()[0]
            cur.execute(
                f"select source_table, count(*) from {APP_SCHEMA}.document_chunks "
                f"group by source_table order by source_table"
            )
            breakdown = cur.fetchall()

        print(f"\nDone. document_chunks now holds {total} rows.")
        for t, n in breakdown:
            print(f"  {t:34} {n}")


if __name__ == "__main__":
    main()
