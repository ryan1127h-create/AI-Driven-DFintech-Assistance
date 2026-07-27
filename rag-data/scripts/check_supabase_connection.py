from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from dotenv import load_dotenv


APP_SCHEMA = "app"

TABLES = [
    "admissions_items",
    "application_status_translations",
    "career_role_modules",
    "career_roles",
    "competitor_programs",
    "course_corrections_log",
    "courses",
    "document_chunks",
    "import_runs",
    "knowledge_snippets",
    "module_skills",
    "programme_pages",
    "skills",
    "source_documents",
]

EXPECTED_COUNTS = {
    "admissions_items": 11,
    "application_status_translations": 8,
    "career_roles": 6,
    "career_role_modules": 44,
    "competitor_programs": 5,
    "course_corrections_log": 47,
    "courses": 72,
    "document_chunks": 0,
    "import_runs": 0,
    "knowledge_snippets": 22,
    "module_skills": 173,
    "programme_pages": 10,
    "skills": 9,
    "source_documents": 10,
}

PUBLIC_READ_TABLES = {
    "admissions_items",
    "application_status_translations",
    "career_role_modules",
    "career_roles",
    "competitor_programs",
    "courses",
    "module_skills",
    "programme_pages",
    "skills",
}

INTERNAL_TABLES = {
    "document_chunks",
    "knowledge_snippets",
    "source_documents",
    "course_corrections_log",
    "import_runs",
}


@dataclass
class CountResult:
    table: str
    actual: int
    expected: int | None

    @property
    def ok(self) -> bool:
        return self.expected is None or self.actual == self.expected


def get_database_url() -> str:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit(
            "DATABASE_URL is missing. Copy .env.example to .env and paste the "
            "Supabase PostgreSQL connection string."
        )
    return database_url


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def check_counts(conn: psycopg.Connection) -> list[CountResult]:
    results: list[CountResult] = []
    with conn.cursor() as cur:
        for table in TABLES:
            sql = f"select count(*) from {quote_ident(APP_SCHEMA)}.{quote_ident(table)}"
            cur.execute(sql)
            actual = cur.fetchone()[0]
            results.append(CountResult(table, actual, EXPECTED_COUNTS.get(table)))
    return results


def check_rls(conn: psycopg.Connection) -> list[tuple[str, bool]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select tablename, rowsecurity
            from pg_tables
            where schemaname = %s
            order by tablename
            """,
            (APP_SCHEMA,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def check_public_policies(conn: psycopg.Connection) -> list[tuple[str, str, str, list[str]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select tablename, policyname, cmd, roles
            from pg_policies
            where schemaname = %s
            order by tablename, policyname
            """,
            (APP_SCHEMA,),
        )
        return [(row[0], row[1], row[2], list(row[3])) for row in cur.fetchall()]


def print_counts(results: list[CountResult]) -> None:
    print("\nRow counts")
    print("-" * 72)
    for result in results:
        expected = "-" if result.expected is None else str(result.expected)
        status = "OK" if result.ok else "CHECK"
        print(f"{result.table:36} actual={result.actual:<5} expected={expected:<5} {status}")


def print_rls(rows: list[tuple[str, bool]]) -> None:
    print("\nRLS status")
    print("-" * 72)
    for table, enabled in rows:
        status = "OK" if enabled else "CHECK"
        print(f"{table:36} rowsecurity={str(enabled):<5} {status}")


def print_policies(policies: list[tuple[str, str, str, list[str]]]) -> None:
    print("\nPolicies")
    print("-" * 72)
    for table, policy, cmd, roles in policies:
        print(f"{table:36} {cmd:8} {policy} roles={roles}")

    public_tables = {
        table for table, _, cmd, roles in policies
        if cmd == "SELECT" and "anon" in roles
    }
    missing_public = sorted(PUBLIC_READ_TABLES - public_tables)
    unexpected_public = sorted(public_tables & INTERNAL_TABLES)

    print("\nPolicy checks")
    print("-" * 72)
    print("Missing public read policies:", missing_public or "none")
    print("Internal tables exposed to anon:", unexpected_public or "none")


def main() -> None:
    database_url = get_database_url()
    with psycopg.connect(database_url) as conn:
        print("Connected to Supabase PostgreSQL.")
        print_counts(check_counts(conn))
        print_rls(check_rls(conn))
        print_policies(check_public_policies(conn))


if __name__ == "__main__":
    main()
