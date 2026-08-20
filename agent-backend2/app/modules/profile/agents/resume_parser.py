"""Resume file -> plain text extraction. Supports PDF and DOCX; the actual
profile extraction from that text happens in
app/modules/profile/agents/resume_agent.py."""

from __future__ import annotations

import io

# Public — api.py derives its upload-validation suffix list from this, so
# there's one source of truth for "which resume formats does this module
# support" instead of two lists that could drift apart.
SUPPORTED_EXTENSIONS = ("pdf", "docx")


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    if ext == "docx":
        return _extract_docx(file_bytes)
    raise ValueError(
        f"Unsupported resume file type '.{ext}' — expected one of: {SUPPORTED_EXTENSIONS}"
    )


def _extract_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)
