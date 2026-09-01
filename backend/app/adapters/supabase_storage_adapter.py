"""
Supabase Storage adapter for ObjectStoragePort. Uses the service_role key
(not anon) so the backend can read/write a bucket directly without
depending on Row Level Security policies — the backend process itself is
trusted to enforce access rules, the same way every relational repository
in this app already is.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.core.config import settings
from app.ports.object_storage_port import ObjectStoragePort


class SupabaseStorageAdapter(ObjectStoragePort):
    def __init__(self, url: str, service_key: str) -> None:
        self._url = url
        self._service_key = service_key
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = create_client(self._url, self._service_key)
        return self._client

    def _ensure_bucket(self, bucket: str) -> None:
        """Creates the bucket if it doesn't exist yet. Idempotent, so this
        can run before every upload with no extra bookkeeping. Buckets are
        created private — reads should go through download(), not a public
        URL."""
        client = self._get_client()
        existing = {b.name for b in client.storage.list_buckets()}
        if bucket not in existing:
            client.storage.create_bucket(bucket, options={"public": False})

    def upload(self, bucket: str, path: str, content: bytes, content_type: str | None) -> None:
        self._ensure_bucket(bucket)
        self._get_client().storage.from_(bucket).upload(
            path,
            content,
            file_options={"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )

    def download(self, bucket: str, path: str) -> bytes:
        return self._get_client().storage.from_(bucket).download(path)


storage = SupabaseStorageAdapter(settings.supabase_url, settings.supabase_service_key)
