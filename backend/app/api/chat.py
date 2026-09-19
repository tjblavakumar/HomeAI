from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document
from app.schemas import ChatRequest, ChatResponse, Citation, DocumentSuggestion
from app.services import llm, rag, search_provider

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        intent_data = llm.extract_intent(payload.message)
    except llm.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    intent = intent_data.get("intent", "other")

    if intent == "troubleshoot":
        query = intent_data.get("query") or payload.message
        try:
            chunks = rag.retrieve(query, item_id=payload.item_id)
        except llm.LLMNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if not chunks:
            scope = "this item" if payload.item_id else "your household"
            return ChatResponse(
                reply=(
                    f"I don't have any indexed manuals for {scope} yet. Find and save a "
                    "manual using the chat above, then ask again once it's indexed."
                ),
                intent=intent,
            )

        try:
            answer = rag.generate_answer(query, chunks)
        except llm.LLMNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        doc_ids = {chunk["metadata"]["document_id"] for chunk in chunks}
        cited_docs = db.execute(select(Document).where(Document.id.in_(doc_ids))).scalars()
        citations = [Citation(title=doc.title, source_url=doc.source_url) for doc in cited_docs]

        return ChatResponse(reply=answer, intent=intent, citations=citations)

    if intent != "find_docs":
        return ChatResponse(
            reply=(
                "I can help find manuals, troubleshooting guides, drivers, and "
                'accessories. Try: "find the manual for my Canon GX1020 printer".'
            ),
            intent=intent,
        )

    product_name = intent_data.get("product_name") or " ".join(
        part for part in [intent_data.get("brand"), intent_data.get("model")] if part
    )
    if not product_name:
        return ChatResponse(
            reply="Which product would you like documents for? Include the brand and model.",
            intent=intent,
        )

    query = intent_data.get("query") or f"{product_name} user manual driver accessories"
    raw_results = search_provider.search_with_fallback(query, max_results=8)
    if not raw_results:
        return ChatResponse(
            reply=f'I couldn\'t find anything online for "{product_name}". Try refining the brand/model.',
            intent=intent,
        )

    try:
        categorized = llm.categorize_search_results(
            product_name,
            [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in raw_results],
        )
    except llm.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    documents = [DocumentSuggestion(**doc) for doc in categorized]

    return ChatResponse(
        reply=f"Here's what I found for {product_name}. Check the ones you'd like to save.",
        intent=intent,
        documents=documents,
    )
