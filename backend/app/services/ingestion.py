from __future__ import annotations

import io
from pathlib import Path

import httpx
import pypdf
import trafilatura

from app.config import settings
from app.db import SessionLocal
from app.models import Document
from app.services import llm
from app.services.vector_store import get_manuals_collection

USER_AGENT = "HomeAI/0.1 (household knowledge base; +local)"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def download_document(url: str) -> tuple[bytes, str]:
    with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        return response.content, content_type


def extract_text(content: bytes, content_type: str) -> str:
    if "pdf" in content_type.lower():
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    html = content.decode("utf-8", errors="ignore")
    extracted = trafilatura.extract(html)
    return extracted or ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def save_to_disk(document_id: int, content: bytes, content_type: str) -> str:
    ext = "pdf" if "pdf" in content_type.lower() else "html"
    path = Path(settings.uploads_dir) / f"document_{document_id}.{ext}"
    path.write_bytes(content)
    return str(path)


def process_document(document_id: int) -> None:
    """Download, extract, chunk, embed, and index a saved (non-driver) document.

    Runs in a FastAPI BackgroundTask, so it opens its own DB session.
    """
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return
        try:
            content, content_type = download_document(document.source_url)
            local_path = save_to_disk(document_id, content, content_type)
            document.local_path = local_path
            document.indexed_status = "downloaded"
            db.commit()

            text = extract_text(content, content_type)
            chunks = chunk_text(text)
            if not chunks:
                document.indexed_status = "failed"
                db.commit()
                return

            embeddings = llm.embed_texts(chunks)
            collection = get_manuals_collection()
            collection.upsert(
                ids=[f"doc{document_id}-chunk{i}" for i in range(len(chunks))],
                embeddings=embeddings,
                documents=chunks,
                metadatas=[
                    {
                        "item_id": document.item_id,
                        "document_id": document_id,
                        "source_url": document.source_url,
                        "chunk_index": i,
                    }
                    for i in range(len(chunks))
                ],
            )
            document.indexed_status = "indexed"
            db.commit()
        except Exception:
            document.indexed_status = "failed"
            db.commit()
    finally:
        db.close()
