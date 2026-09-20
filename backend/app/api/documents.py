from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document, Item
from app.schemas import DocumentOut, DocumentSelectRequest
from app.services.ingestion import process_document

router = APIRouter(tags=["documents"])


@router.post("/documents/select", response_model=list[DocumentOut], status_code=201)
def select_documents(
    payload: DocumentSelectRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> list[Document]:
    item = db.get(Item, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    saved: list[Document] = []
    for doc in payload.documents:
        # Drivers are link-only: never downloaded, never indexed into RAG.
        is_driver = doc.doc_type == "driver"
        document = Document(
            item_id=payload.item_id,
            doc_type=doc.doc_type,
            title=doc.title,
            source_url=doc.source_url,
            indexed_status="link_only" if is_driver else "pending",
        )
        db.add(document)
        db.flush()
        saved.append(document)
        if not is_driver:
            background_tasks.add_task(process_document, document.id)
    db.commit()
    for document in saved:
        db.refresh(document)
    return saved


@router.get("/items/{item_id}/documents", response_model=list[DocumentOut])
def list_documents_for_item(item_id: int, db: Session = Depends(get_db)) -> list[Document]:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return list(db.execute(select(Document).where(Document.item_id == item_id)).scalars())


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.doc_type == "driver":
        raise HTTPException(status_code=400, detail="Driver documents are link-only and cannot be re-indexed")

    # Remove existing Chroma chunks for this document
    if document.indexed_status in ("indexed", "downloaded", "failed"):
        from app.services.vector_store import get_manuals_collection
        col = get_manuals_collection()
        existing_ids = col.get(where={"document_id": document_id})["ids"] or []
        if existing_ids:
            col.delete(ids=existing_ids)

    # Reset status and re-process
    document.indexed_status = "pending"
    document.local_path = None
    db.commit()
    background_tasks.add_task(process_document, document.id)
    return document
