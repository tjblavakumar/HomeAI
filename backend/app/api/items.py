from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.orm import Session
from pathlib import Path as FilePath

from app.db import get_db
from app.models import Category, Document, Item
from app.schemas import ItemCreate, ItemFromUrl, ItemOut, ScanResult
from app.config import settings
from app.services import llm, ocr
from app.services.ingestion import (
    _FILE_TYPE_PDF,
    _guess_file_type,
    _slugify,
    chunk_text,
    extract_text,
    process_document,
    save_to_disk,
)
from app.services.vector_store import get_manuals_collection
import logging
import os
import re
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/from-url", response_model=ItemOut, status_code=201)
def create_item_from_url(
    payload: ItemFromUrl,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Item:
    """Create an item and immediately download + index a manual from *url*."""
    category = db.get(Category, payload.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    item = Item(
        name=payload.name,
        brand=payload.brand,
        model_number=payload.model_number,
        category_id=payload.category_id,
    )
    db.add(item)
    db.flush()

    # Derive a friendly title from the URL filename
    title = _title_from_url(payload.url) or payload.name

    document = Document(
        item_id=item.id,
        doc_type="manual",
        title=title,
        source_url=payload.url,
        indexed_status="pending",
    )
    db.add(document)
    db.flush()

    db.commit()
    db.refresh(item)

    background_tasks.add_task(process_document, document.id)
    return item


@router.post("/upload", response_model=ItemOut, status_code=201)
async def upload_item_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    category_id: int = Form(...),
    brand: str | None = Form(None),
    model_number: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Item:
    """Upload a local PDF file, create an item, and index it into RAG."""
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # Validate it's a PDF
    file_type = _guess_file_type(content, content_type)
    if file_type != _FILE_TYPE_PDF:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are supported, got '{file_type}'",
        )

    # Create the item + document first so we know the document_id for the file path
    item = Item(name=name, brand=brand, model_number=model_number, category_id=category_id)
    db.add(item)
    db.flush()

    doc_title = file.filename or name
    document = Document(
        item_id=item.id,
        doc_type="manual",
        title=doc_title,
        source_url=f"upload://{file.filename or 'manual.pdf'}",
        indexed_status="pending",
    )
    db.add(document)
    db.flush()

    # Save the file to disk (keyed on document.id)
    local_path = save_to_disk(document.id, content, content_type, item_id=item.id, category_name=category.name)
    document.local_path = local_path
    document.indexed_status = "downloaded"

    db.commit()
    db.refresh(item)

    # Index via background task
    background_tasks.add_task(_index_local_document, document.id)
    return item


def _index_local_document(document_id: int) -> None:
    """Index a document whose file is already on disk (uploaded locally)."""
    from app.services.ingestion import chunk_text, extract_text
    from app.services.vector_store import get_manuals_collection
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document or not document.local_path:
            logger.warning("_index_local_document(%s): document or local_path missing", document_id)
            return

        local_path = document.local_path
        # local_path is stored relative to the backend working dir (e.g. "../data/uploads/...")
        resolved = os.path.normpath(os.path.abspath(local_path))
        if not os.path.exists(resolved):
            logger.error("_index_local_document(%s): file not found at %s", document_id, resolved)
            document.indexed_status = "failed"
            db.commit()
            return

        with open(resolved, "rb") as f:
            content = f.read()

        content_type = "application/pdf" if content.startswith(b"%PDF") else "text/plain"
        text = extract_text(content, content_type)
        chunks = chunk_text(text)

        if not chunks:
            logger.error("_index_local_document(%s): no text extracted from uploaded PDF", document_id)
            document.indexed_status = "failed"
            db.commit()
            return

        if document.doc_type == "manual" and len(text.strip()) < 1000:
            logger.error("_index_local_document(%s): only %d chars — too short", document_id, len(text.strip()))
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
        logger.info("_index_local_document(%s): indexed %d chunks", document_id, len(chunks))
    except Exception:
        logger.exception("_index_local_document(%s): failed", document_id)
        try:
            document = db.get(Document, document_id)
            if document:
                document.indexed_status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _title_from_url(url: str) -> str:
    """Extract a human-friendly label from a PDF URL."""
    path = urlparse(url).path
    stem = path.rstrip("/").split("/")[-1] if "/" in path else path
    stem = unquote(stem)   # URL-decode
    stem = re.sub(r"(?i)\.pdf|\.html|\.htm", "", stem)  # drop extension
    stem = re.sub(r"[_-]", " ", stem)                     # split snake/kebab case
    stem = re.sub(r"\s+", " ", stem).strip()              # collapse whitespace
    return stem if len(stem) > 2 else ""


@router.get("", response_model=list[ItemOut])
def list_items(
    category_id: int | None = Query(None),
    doc_type: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Item]:
    query = select(Item)
    if category_id is not None:
        query = query.where(Item.category_id == category_id)
    if doc_type is not None:
        query = query.join(Item.documents).where(Document.doc_type == doc_type)
    return list(db.execute(query).scalars().unique().all())


@router.post("/scan", response_model=ScanResult)
async def scan_item_photo(file: UploadFile) -> ScanResult:
    image_bytes = await file.read()
    try:
        result = ocr.scan_image(image_bytes)
    except ocr.OCRUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ScanResult(**result)


@router.post("", response_model=ItemOut, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)) -> Item:
    category = db.get(Category, payload.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)) -> Item:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Remove document files from disk
    for doc in item.documents:
        if doc.local_path:
            try:
                os.remove(doc.local_path)
            except OSError:
                pass

    # Remove from Chroma (best-effort — collection might not exist yet)
    try:
        from app.services.vector_store import get_manuals_collection
        col = get_manuals_collection()
        # Chroma metadata stores ints as ints, but use the same type for the where clause
        existing = col.get(where={"item_id": item_id})
        existing_ids = existing.get("ids") or []
        if existing_ids:
            col.delete(ids=existing_ids)
    except Exception:
        pass  # Chroma not available / no collection yet

    # Delete documents first, then item
    db.query(Document).where(Document.item_id == item_id).delete()
    db.delete(item)
    db.commit()
