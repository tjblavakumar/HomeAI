from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import httpx
import pypdf
import trafilatura

from app.config import settings
from app.db import SessionLocal
from app.models import Document
from app.services import llm
from app.services.vector_store import get_manuals_collection

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
CHUNK_SIZE = 2500
CHUNK_OVERLAP = 400

# ── helpers ──────────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    """Turn a category name like "Small Appliances" into "small-appliances"."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


_FILE_TYPE_PDF = "pdf"
_FILE_TYPE_HTML = "html"
_FILE_TYPE_TEXT = "text"
_FILE_TYPE_MARKDOWN = "markdown"


def _guess_file_type(content: bytes, content_type: str) -> str:
    """Determine whether *content* is PDF, HTML, plain text, or markdown.

    Uses the Content-Type header first, then falls back to magic-bytes /
    content inspection.
    """
    ct = (content_type or "").lower()

    # 1. Trust explicit Content-Type header
    if "pdf" in ct:
        return _FILE_TYPE_PDF
    if "text/html" in ct:
        return _FILE_TYPE_HTML
    if "text/markdown" in ct or "text/x-markdown" in ct:
        return _FILE_TYPE_MARKDOWN
    if "text/plain" in ct:
        return _FILE_TYPE_TEXT

    # 2. Magic-bytes / content inspection
    if content.startswith(b"%PDF"):
        return _FILE_TYPE_PDF

    # Check whether the first non-blank bytes look like HTML
    decoded_preview = content[:2000].decode("utf-8", errors="ignore").strip().lower()
    if decoded_preview.startswith("<html") or decoded_preview.startswith("<!doctype"):
        return _FILE_TYPE_HTML

    # If it doesn't look like HTML, treat it as plain text
    return _FILE_TYPE_TEXT


def download_document(url: str) -> tuple[bytes, str]:
    with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        content = response.content

    # If the response is HTML but the URL looks like a PDF (e.g. an interstitial
    # page that wraps an embedded <object>/<embed>/<iframe> PDF), try to extract
    # a direct PDF link from the page and re-download.
    if "text/html" in content_type.lower() and not content.startswith(b"%PDF"):
        pdf_url = _extract_pdf_url_from_html(content)
        if pdf_url:
            with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(pdf_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                content = response.content

    return content, content_type


def _extract_pdf_url_from_html(content: bytes) -> str | None:
    """Look for the first PDF URL in <object>, <embed>, <iframe>, or <a> within *content*."""
    import re
    html = content.decode("utf-8", errors="ignore")

    # Priority 1: <object data="...pdf" ...>
    m = re.search(r'<object\s[^>]*data\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)

    # Priority 2: <embed src="...pdf" ...>
    m = re.search(r'<embed\s[^>]*src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)

    # Priority 3: <iframe src="...pdf" ...>
    m = re.search(r'<iframe\s[^>]*src\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)

    # Priority 4: any <a href="...pdf"...>
    m = re.search(r'<a\s[^>]*href\s*=\s*["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I)
    if m:
        return m.group(1)

    return None


def extract_text(content: bytes, content_type: str) -> str:
    file_type = _guess_file_type(content, content_type)

    if file_type == _FILE_TYPE_PDF:
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if file_type in (_FILE_TYPE_TEXT, _FILE_TYPE_MARKDOWN):
        return content.decode("utf-8", errors="ignore")

    # HTML – use trafilatura
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


def save_to_disk(
    document_id: int,
    content: bytes,
    content_type: str,
    item_id: int,
    category_name: str,
) -> str:
    """Write *content* to ``data/uploads/{category_slug}/{item_id}/``.

    Returns the absolute local path stored in the DB.
    """
    file_type = _guess_file_type(content, content_type)
    ext = {
        _FILE_TYPE_PDF: "pdf",
        _FILE_TYPE_HTML: "html",
        _FILE_TYPE_TEXT: "txt",
        _FILE_TYPE_MARKDOWN: "md",
    }.get(file_type, "txt")

    category_slug = _slugify(category_name)
    dest_dir = Path(settings.uploads_dir) / category_slug / str(item_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"document_{document_id}.{ext}"
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
            logger.warning("process_document(%s): document not found", document_id)
            return

        # Resolve item + category for folder structure
        item = document.item
        if item is None:
            logger.warning("process_document(%s): item not found", document_id)
            return
        category = item.category
        category_name = category.name if category else "Uncategorized"

        try:
            logger.info("process_document(%s): downloading %s", document_id, document.source_url)
            content, content_type = download_document(document.source_url)
            local_path = save_to_disk(
                document_id, content, content_type,
                item_id=item.id, category_name=category_name,
            )
            document.local_path = local_path
            document.indexed_status = "downloaded"
            db.commit()
            logger.info("process_document(%s): downloaded → %s", document_id, local_path)

            logger.info("process_document(%s): extracting text", document_id)
            text = extract_text(content, content_type)
            chunks = chunk_text(text)
            if not chunks:
                logger.error(
                    "process_document(%s): extracted text is empty — the source URL "
                    "did not return a downloadable document (got %s, length %d)",
                    document_id, content_type, len(content),
                )
                document.indexed_status = "failed"
                db.commit()
                return

            # Minimum-text guard: a manual with fewer than 1000 chars of content
            # is almost certainly an interstitial / login wall and not the real doc.
            if document.doc_type == "manual" and len(text.strip()) < 1000:
                logger.error(
                    "process_document(%s): only %d chars extracted from manual — "
                    "likely an interstitial page, marking failed",
                    document_id, len(text.strip()),
                )
                document.indexed_status = "failed"
                db.commit()
                return

            logger.info("process_document(%s): embedding %d chunks", document_id, len(chunks))
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
            logger.info("process_document(%s): indexed successfully", document_id)
        except Exception:
            logger.exception("process_document(%s): failed", document_id)
            document.indexed_status = "failed"
            db.commit()
    finally:
        db.close()
