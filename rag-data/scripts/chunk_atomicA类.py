"""A-class chunking: atomic tables -> one row = one chunk -> embed -> load.

Six tables whose rows are already self-contained facts, so each row becomes a
single chunk. Context prefixes are built from fields (no LLM). The embedding
input is (context + "\n" + content), per Anthropic contextual retrieval.

Reads the LIVE database, not the CSV snapshots -- the exports are stale (deleted
demo/NUS rows) and Supabase truncates CSV export to the first 100 rows.

    python scripts/chunk_atomic.py --dry-run          # build + print, no OpenAI, no write
    python scripts/chunk_atomic.py --only courses      # one table
    python scripts/chunk_atomic.py                     # embed all + upsert

Re-running upserts on chunk_key, so it refreshes rather than duplicates.
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
EMBED_BATCH = 128
PROGRAMME = "NUS MSc Digital Financial Technology (MSc DFinTech)"
FAQ_URL = "https://www.comp.nus.edu.sg/programmes/pg/mdft/faq/"

# The FAQ's test-score answer conflicts with the Admission Requirements page
# ("minimum GMAT 650"). Per the recorded decision the FAQ wins; the admissions
# page chunk (B-class) will carry the same group with authoritative=false.
CONFLICT_TEST_SCORE = "test_score_requirement"


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


def clean(s: str | None) -> str:
    return (s or "").strip()


# Populated by load_course_skills() before build_courses() runs:
# course_code -> "AI / Machine Learning (machine learning, 机器学习); Finance ...".
# Aliases (incl. Chinese) are folded in so a Chinese query can hit an English
# course chunk directly.
_COURSE_SKILLS: dict[str, str] = {}


def load_course_skills(conn: psycopg.Connection) -> None:
    """Build course_code -> skill-label string from module_skills + skills."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select ms.module_code, s.label, s.aliases
            from {APP_SCHEMA}.module_skills ms
            join {APP_SCHEMA}.skills s on s.id = ms.skill_id
            order by ms.module_code, s.label
        """)
        rows = cur.fetchall()

    by_course: dict[str, list[str]] = {}
    for r in rows:
        aliases = ", ".join(a for a in (r["aliases"] or []) if a)
        label = r["label"] + (f" ({aliases})" if aliases else "")
        by_course.setdefault(r["module_code"], []).append(label)

    _COURSE_SKILLS.clear()
    for code, labels in by_course.items():
        _COURSE_SKILLS[code] = "; ".join(labels)


# --- per-table builders -----------------------------------------------------

def build_courses(rows: list[dict]) -> list[Chunk]:
    out = []
    for r in rows:
        code = r["course_code"]
        title = clean(r["title"])
        units = r["module_credit"]
        parts = [f"{code} {title} ({units} units)."]
        parts.append(f"Faculty: {clean(r['faculty'])}, {clean(r['department'])}.")
        if clean(r["description"]):
            parts.append(f"Description: {clean(r['description'])}")
        if clean(r["prerequisite"]):
            parts.append(f"Prerequisite: {clean(r['prerequisite'])}")
        if clean(r["preclusion"]):
            parts.append(f"Preclusion: {clean(r['preclusion'])}")
        skills = _COURSE_SKILLS.get(code)
        if skills:
            parts.append(f"Skills covered: {skills}.")
        content = " ".join(parts)

        context = (
            f'This describes course {code} "{title}", a {units}-unit course '
            f"relevant to the {PROGRAMME}. Useful for questions about this "
            f"course's content, prerequisites, skills taught, and course recommendation."
        )
        out.append(Chunk(
            chunk_key=f"course:{code}",
            source_table="courses",
            source_id=code,
            content=content,
            context=context,
            answer_type="official",
            metadata={
                "annex_presence": r["annex_presence"],
                "annex_section": r["annex_section"],   # hint only; not authoritative for core/elective
                "can_recommend": r["can_recommend"],
                "faculty": clean(r["faculty"]),
                "semester_count": r["semester_count"],
                "source_url": clean(r["source_url"]),
            },
        ))
    return out


def build_knowledge_snippets(rows: list[dict]) -> list[Chunk]:
    ns_context = {
        "faq_web": "Official FAQ answer from the NUS MSc DFinTech programme website.",
        "faq": "Curated FAQ fact about the NUS MSc DFinTech programme.",
        "admissions": "Application requirement note for the NUS MSc DFinTech programme.",
    }
    out = []
    for r in rows:
        sid = r["id"]
        ns = r["namespace"]
        context = ns_context.get(ns, f"Knowledge snippet ({ns}) about the {PROGRAMME}.")

        conflict = None
        if sid == "faq_web_cut_off_average_score":
            conflict = CONFLICT_TEST_SCORE

        out.append(Chunk(
            chunk_key=f"snippet:{sid}",
            source_table="knowledge_snippets",
            source_id=sid,
            content=clean(r["text"]),
            context=context,
            answer_type=clean(r["source_type"]) or "official",
            conflict_group=conflict,
            authoritative=True,
            metadata={
                "namespace": ns,
                "source_id": clean(r["source_id"]),
                "source_url": FAQ_URL if ns == "faq_web" else None,
            },
        ))
    return out


def build_course_rules(rows: list[dict]) -> list[Chunk]:
    out = []
    for r in rows:
        rid = r["id"]
        context = (
            f"Curriculum rule ({r['category']}) for the {PROGRAMME}, "
            f"applicable to the {r['intake']} intake."
        )
        out.append(Chunk(
            chunk_key=f"rule:{rid}",
            source_table="course_rules",
            source_id=rid,
            content=clean(r["text"]),
            context=context,
            answer_type=clean(r.get("source_type")) or "official",
            metadata={"intake": r["intake"], "category": r["category"]},
        ))
    return out


def build_admissions_items(rows: list[dict]) -> list[Chunk]:
    out = []
    for r in rows:
        key = r["key"]
        label = clean(r["label"])
        status = "Required" if r["required"] else "Optional or conditional"
        content = f"{label} — {status}. {clean(r['why'])}"
        context = (
            f"Application document requirement for the {PROGRAMME}: "
            f'"{label}". Useful for the application checklist and what to submit.'
        )
        out.append(Chunk(
            chunk_key=f"admission:{key}",
            source_table="admissions_items",
            source_id=key,
            content=content,
            context=context,
            answer_type="official",
            metadata={"required": r["required"], "deadline_key": clean(r["deadline_key"])},
        ))
    return out


def build_status_translations(rows: list[dict]) -> list[Chunk]:
    out = []
    for r in rows:
        code = r["status_code"]
        content = f'Application status "{clean(r["human_status"])}". Next step: {clean(r["next_step"])}'
        if r.get("eta_days"):
            content += f" (typically about {r['eta_days']} days)."
        context = (
            f"NUS MSc DFinTech application status explanation for {code}. "
            f"Useful for application tracking and understanding what a status means."
        )
        out.append(Chunk(
            chunk_key=f"status:{code}",
            source_table="application_status_translations",
            source_id=code,
            content=content,
            context=context,
            answer_type="official",
            metadata={"status_code": code, "eta_days": r.get("eta_days")},
        ))
    return out


def render_value(v) -> str:
    """A competitor field is either a plain string (a real fact) or
    {kind: unknown|synthesis, text}. Make the provenance explicit."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        kind, text = v.get("kind"), clean(v.get("text"))
        if kind == "unknown":
            return f"(not stated on the official comparison page) {text}"
        return text  # synthesis
    return ""


def build_competitor_programs(rows: list[dict]) -> list[Chunk]:
    fields = [
        ("Fees", "fees"), ("Format", "format"), ("Intake", "intake"),
        ("Duration", "duration"), ("GMAT/GRE", "gmat_gre"),
        ("Scholarship", "scholarship"), ("Curriculum focus", "curriculum_focus"),
        ("Typical profile", "typical_profile"), ("Technical depth", "technical_depth"),
        ("Career pathways", "career_pathways"), ("Industry orientation", "industry_orientation"),
    ]
    out = []
    for r in rows:
        name = clean(r["program_name"])
        vals = r["values"] or {}
        lines = [f"{label}: {render_value(vals[k])}" for label, k in fields if k in vals]
        content = f"{name}. " + " ".join(lines)
        context = (
            f"Competitor programme comparison: {name}. Useful for questions "
            f"comparing the {PROGRAMME} with other FinTech master's programmes."
        )
        out.append(Chunk(
            chunk_key=f"competitor:{name}",
            source_table="competitor_programs",
            source_id=str(r["id"]),
            content=content,
            context=context,
            answer_type="advisory",  # comparison data, much of it synthesised
            metadata={"is_target": r["is_target"], "source_url": clean(r["source_url"])},
        ))
    return out


BUILDERS = {
    "courses": build_courses,
    "knowledge_snippets": build_knowledge_snippets,
    "course_rules": build_course_rules,
    "admissions_items": build_admissions_items,
    "application_status_translations": build_status_translations,
    "competitor_programs": build_competitor_programs,
}


# --- embedding + load -------------------------------------------------------

def fetch(conn: psycopg.Connection, table: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f'select * from {APP_SCHEMA}."{table}"')
        return cur.fetchall()


def embed(client, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
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
                "token_count": len(chunk.embed_input.split()),
                "answer_type": chunk.answer_type,
                "conflict_group": chunk.conflict_group,
                "authoritative": chunk.authoritative,
                "metadata": Jsonb({k: v for k, v in chunk.metadata.items() if v is not None}),
            })
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=list(BUILDERS), help="chunk just one table")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and print chunks; no OpenAI call, no write")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. See .env.example.")

    tables = [args.only] if args.only else list(BUILDERS)

    with psycopg.connect(database_url) as conn:
        if "courses" in tables:
            load_course_skills(conn)  # course chunks get a skills line

        all_chunks: list[Chunk] = []
        for table in tables:
            rows = fetch(conn, table)
            chunks = BUILDERS[table](rows)
            all_chunks.extend(chunks)
            print(f"{table:34} {len(rows):>3} rows -> {len(chunks):>3} chunks")

        print(f"\nTotal: {len(all_chunks)} chunks")

        if args.dry_run:
            print("\n--- sample chunks (first of each table) ---")
            seen = set()
            for c in all_chunks:
                if c.source_table in seen:
                    continue
                seen.add(c.source_table)
                print(f"\n[{c.chunk_key}]  answer_type={c.answer_type}"
                      f"{'  conflict='+c.conflict_group if c.conflict_group else ''}")
                print(f"  context: {c.context}")
                print(f"  content: {c.content[:200]}{'...' if len(c.content) > 200 else ''}")
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
