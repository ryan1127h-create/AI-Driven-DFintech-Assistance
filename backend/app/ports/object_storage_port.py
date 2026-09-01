"""
Contract for an object store that can upload (or overwrite) and download a
byte blob by path within a named bucket.
"""

from __future__ import annotations

from typing import Protocol


class ObjectStoragePort(Protocol):
    def upload(self, bucket: str, path: str, content: bytes, content_type: str | None) -> None:
        """Uploads (or fully overwrites) the object at path within bucket."""
        ...

    def download(self, bucket: str, path: str) -> bytes:
        """Returns the exact bytes previously uploaded at path."""
        ...
