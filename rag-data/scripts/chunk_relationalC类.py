"""C-class chunking: relational tables -> aggregated role chunks -> embed -> load.

career_roles already carries everything a career chunk needs -- title, required
skills, and recommended modules (in its raw JSON). So each of the 6 roles
becomes one chunk aggregating role + skills + recommended courses. The detail
tables career_role_modules (44) and module_skills (173) are NOT chunked
separately: the first duplicates career_roles.raw, the second is folded into the
course chunks (chunk_atomicA类.py adds a "Skills covered" line per course).

Skill labels are enriched with their aliases (incl. Chinese) from the skills
table so a Chinese query can hit these English chunks.

    python scripts/chunk_relationalC类.py --dry-run
    python scripts/chunk_relationalC类.py
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

APP_SCHEMA = "app"
EMBED_MODEL = "text-embedding-3-small"
PROGRAMME = "NUS MSc Digital Financial Technology (MSc DFinTech)"


@dataclass
class Chunk:
    chunk_key: str
    source_table: str
    source_id: str
    content: str
    context: str
    answer_type: str = "advisory"
    conflict_group: str | None = None
    authoritative: bool = True
    metadata: dict = field(default_factory=dict)

    @property
    def embed_input(self) -> str:
        return f"{self.context}\n{self.content}"


def load_skill_labels(conn: psycopg.Connection) -> dict[str, str]:
    """skill_id -> 'Label (alias1, alias2, 中文)'."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"select id, label, aliases from {APP_SCHEMA}.skills")
        out = {}
        for r in cur.fetchall():
            aliases = ", ".join(a for a in (r["aliases"] or []) if a)
            out[r["id"]] = r["label"] + (f" ({aliases})" if aliases else "")
        return out


def build_role_chunks(conn: psycopg.Connection) -> list[Chunk]:
    skill_label = load_skill_labels(conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"select role_id, title, required_skills, raw from {APP_SCHEMA}.career_roles order by role_id")
        roles = cur.fetchall()

    chunks: list[Chunk] = []
    for r in roles:
        role_id = r["role_id"]
        title = r["title"]
        raw = r["raw"] or {}

        skills = [skill_label.get(s, s) for s in (r["required_skills"] or [])]
        modules = raw.get("recommended_modules", [])
        mod_str = ", ".join(f"{m['code']} {m['name']}" for m in modules)

        content = (
            f"Career track: {title} ({role_id}) for graduates of the {PROGRAMME}. "
            f"Key skills for this role: {'; '.join(skills)}. "
            f"Recommended modules for this career path: {mod_str}."
        )
        context = (
            f'This describes the "{title}" career track in the {PROGRAMME}. '
            f"Useful for questions about career paths, which courses to take for a "
            f"target job role, and skill requirements."
        )
        chunks.append(Chunk(
            chunk_key=f"role:{role_id}",
            source_table="career_roles",
            source_id=role_id,
            content=content,
            context=context,
            answer_type="advisory",  # career guidance, not official policy
            metadata={
                "role_id": role_id,
                "role_title": title,
                "required_skills": r["required_skills"],
            },
        ))
    return chunks


def embed(client, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


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
                "token_count": len(chunk.embed_input.split()),
                "answer_type": chunk.answer_type,
                "conflict_group": chunk.conflict_group,
                "authoritative": chunk.authoritative,
                "metadata": Jsonb({k: v for k, v in chunk.metadata.items() if v is not None}),
            })
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. See .env.example.")

    with psycopg.connect(database_url) as conn:
        chunks = build_role_chunks(conn)
        print(f"Built {len(chunks)} role chunks from career_roles")

        if args.dry_run:
            for c in chunks:
                print(f"\n[{c.chunk_key}]")
                print(f"  context: {c.context}")
                print(f"  content: {c.content}")
            print("\nDRY RUN: nothing embedded or written.")
            return

        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise SystemExit("OPENAI_API_KEY is missing. See .env.example.")
        from openai import OpenAI
        client = OpenAI(api_key=key)

        print(f"Embedding {len(chunks)} chunks with {EMBED_MODEL}...")
        vectors = embed(client, [c.embed_input for c in chunks])

        print("Writing to document_chunks...")
        upsert(conn, chunks, vectors)

        with conn.cursor() as cur:
            cur.execute(f"select count(*) from {APP_SCHEMA}.document_chunks")
            total = cur.fetchone()[0]
            cur.execute(f"select source_table, count(*) from {APP_SCHEMA}.document_chunks group by source_table order by source_table")
            breakdown = cur.fetchall()

        print(f"\nDone. document_chunks now holds {total} rows.")
        for t, n in breakdown:
            print(f"  {t:34} {n}")


if __name__ == "__main__":
    main()
