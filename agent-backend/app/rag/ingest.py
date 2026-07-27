"""
Document ingestion pipeline — section-aware, with domain metadata.

Run this script ONCE before starting the server to populate ChromaDB:
  python app/rag/ingest.py

Re-run whenever documents in the data/ folder are updated.
Each run wipes and rebuilds the vector store from scratch.
"""

import os
import re
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings

DATA_DIR    = PROJECT_ROOT / "data"
CHROMA_DIR  = PROJECT_ROOT / "chroma_db"
COLLECTION  = "msc_dft_knowledge"
EMBED_MODEL = "all-MiniLM-L6-v2"

# Maps knowledge-base section names → retrieval domain used by agents
SECTION_DOMAIN_MAP = {
    "Programme Overview":         "academic",
    "Programme Structure":        "academic",
    "Admissions Requirements":    "admissions",
    "Application":                "admissions",
    "Tuition Fees":               "financial",
    "Scholarships":               "financial",
    "Capstone Project":           "academic",
    "Core and Essential Courses": "academic",
    "Elective Tracks":            "academic",
    "Course Preclusions":         "academic",
    "Suggested Course Plans":     "academic",
}

_SECTION_RE = re.compile(r"=== SECTION:\s*(.+?)\s*===")


def _parse_txt_sections(text: str, source_name: str) -> list[Document]:
    """
    Split a text file at '=== SECTION: ... ===' markers.
    Each section becomes one Document tagged with section + domain metadata.
    Falls back to a single Document if no markers are found.
    """
    parts = _SECTION_RE.split(text)

    # parts layout: [pre-header, name1, content1, name2, content2, ...]
    if len(parts) < 3:
        return [Document(
            page_content=text.strip(),
            metadata={"source": source_name, "section": "General", "domain": "general"},
        )]

    documents = []
    for i in range(1, len(parts), 2):
        section_name = parts[i].strip()
        content      = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not content:
            continue
        domain = SECTION_DOMAIN_MAP.get(section_name, "general")
        documents.append(Document(
            page_content=content,
            metadata={"source": source_name, "section": section_name, "domain": domain},
        ))
        print(f"    Section '{section_name}' → domain='{domain}'")

    return documents


def load_documents() -> list[Document]:
    """Load .txt files (section-aware) and .pdf files from data/."""
    documents = []
    txt_files = list(DATA_DIR.glob("*.txt"))
    pdf_files = list(DATA_DIR.glob("*.pdf"))

    if not txt_files and not pdf_files:
        print(f"[ERROR] No .txt or .pdf files found in: {DATA_DIR}")
        sys.exit(1)

    for filepath in txt_files:
        print(f"  Loading (txt, section-aware): {filepath.name}")
        try:
            text = filepath.read_text(encoding="utf-8")
            docs = _parse_txt_sections(text, filepath.name)
            documents.extend(docs)
        except Exception as exc:
            print(f"  [WARNING] Failed to load {filepath.name}: {exc}")

    for filepath in pdf_files:
        print(f"  Loading (pdf): {filepath.name}")
        try:
            loader = PyPDFLoader(str(filepath))
            docs = loader.load()
            for doc in docs:
                doc.metadata.update({"source": filepath.name, "domain": "general"})
            documents.extend(docs)
        except Exception as exc:
            print(f"  [WARNING] Failed to load {filepath.name}: {exc}")

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """Split documents into overlapping chunks; metadata is preserved per chunk."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " "],
    )
    return splitter.split_documents(documents)


def build_vectorstore(chunks: list[Document]) -> None:
    """Embed chunks and persist to ChromaDB."""
    print(f"\n  Loading embedding model '{EMBED_MODEL}' ...")
    print("  (First run downloads ~90 MB — one-time step.)")
    embeddings = SentenceTransformerEmbeddings(model_name=EMBED_MODEL)

    print(f"  Writing {len(chunks)} chunks to ChromaDB at: {CHROMA_DIR}")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION,
    )


def main():
    print("=" * 50)
    print("  MSc DFT — RAG Ingestion Pipeline")
    print("=" * 50)

    if CHROMA_DIR.exists():
        print(f"\n  Removing existing ChromaDB at: {CHROMA_DIR}")
        shutil.rmtree(CHROMA_DIR)

    print("\n[1/3] Loading documents from data/ ...")
    documents = load_documents()
    print(f"  Loaded {len(documents)} section document(s)")

    print("\n[2/3] Splitting into chunks ...")
    chunks = split_documents(documents)
    print(f"  Created {len(chunks)} chunks")

    print("\n[3/3] Embedding and storing in ChromaDB ...")
    build_vectorstore(chunks)

    print("\n[DONE] Knowledge base is ready.")
    print(f"       ChromaDB stored at: {CHROMA_DIR}")
    print("       You can now start the server.\n")


if __name__ == "__main__":
    main()
