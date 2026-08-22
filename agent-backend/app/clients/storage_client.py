"""
Supabase Storage client — object storage for checklist file uploads (see
app/modules/checklist/service.py). Replaces the previous approach of writing
the raw file bytes into a Postgres `bytea` column: files now live in a
Storage bucket, and the database only keeps the object path.

Uses the service_role key (not anon) so the backend can read/write the
bucket directly without depending on Row Level Security policies — this
mirrors how every other repository in the app already trusts the backend
process itself to enforce access rules, not the database/storage layer.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.core.config import settings

_client: Client | None = None


def get_storage_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


def ensure_bucket(bucket: str) -> None:
    """Creates the bucket if it doesn't exist yet. Idempotent — safe to call
    on every upload without extra bookkeeping. Private bucket (not publicly
    readable): access should go through download_file() below, not a public URL."""
    client = get_storage_client()
    existing = {b.name for b in client.storage.list_buckets()}
    if bucket not in existing:
        client.storage.create_bucket(bucket, options={"public": False})


def upload_file(bucket: str, path: str, content: bytes, content_type: str | None) -> None:
    """Uploads (or overwrites) one object. upsert=true because a checklist
    item's file is meant to be fully replaced on re-upload, matching the
    previous bytea column's overwrite semantics."""
    ensure_bucket(bucket)
    get_storage_client().storage.from_(bucket).upload(
        path, content,
        file_options={"content-type": content_type or "application/octet-stream", "upsert": "true"},
    )


def download_file(bucket: str, path: str) -> bytes:
    """Returns the exact bytes previously uploaded at `path`."""
    return get_storage_client().storage.from_(bucket).download(path)
