from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document
from app.schemas import ChatRequest, ChatResponse, Citation, DocumentSuggestion
from app.services import llm, rag, search_provider

import re

router = APIRouter(prefix="/chat", tags=["chat"])

_STOPWORDS = {
    "how", "the", "and", "for", "with", "what", "where", "when",
    "why", "can", "you", "not", "from", "this", "that", "are",
    "its", "has", "have", "was", "were", "will", "would",
    "could", "should", "about", "does", "doing", "done", "get",
    "got", "all", "any", "been", "but", "did", "each", "had",
    "him", "his", "may", "more", "now", "out", "say", "she",
    "some", "than", "too", "very", "who",
}


def _resolve_rag_items(query: str, db: Session) -> list[int]:
    """Find the saved items that best match the user's question by keyword overlap.

    Searches against each item's name, brand, model number **and** the titles of
    its saved documents. Returns **all** items tied for the top score so the RAG
    search covers every candidate (avoids an old duplicate item with no indexed
    chunks shadowing a newer one).

    Returns an empty list to search across all items.
    """
    from app.models import Item as ItemModel  # avoid circular import at module level

    all_items = db.execute(select(ItemModel)).scalars().all()
    if not all_items:
        return []

    # Extract meaningful words (≥3 chars, not stopwords)
    query_lower = query.lower()
    query_words = {m.group() for m in re.finditer(r"\b[a-z]{3,}\b", query_lower)} - _STOPWORDS
    if not query_words:
        return []

    scores: dict[int, int] = {}
    for item in all_items:
        # Build a rich searchable string from the item + its document titles
        doc_titles = " ".join(d.title for d in (item.documents or []))
        target = " ".join([
            item.name or "",
            item.brand or "",
            item.model_number or "",
            doc_titles,
        ]).lower()

        score = 0
        for qw in query_words:
            # Prefer whole-word matches, also accept substring for compounds
            if re.search(rf"\b{re.escape(qw)}\b", target):
                score += 2
            elif qw in target:
                score += 1
        if score > 0:
            scores[item.id] = score

    if not scores:
        return []

    best = max(scores.values())
    if best < 2:
        return []
    return [item_id for item_id, s in scores.items() if s == best]


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        intent_data = llm.extract_intent(payload.message)
    except llm.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    intent = intent_data.get("intent", "other")

    # ── RAG mode: only troubleshoot, no web search ──────────────────
    if payload.mode == "rag":
        if intent != "troubleshoot":
            return ChatResponse(
                reply=(
                    "I can only answer questions from your household's saved and indexed "
                    'manuals. Try: "how to clean the coffee machine", or ask about a specific '
                    "troubleshooting topic. To find and save new manuals, go to the Add Item page."
                ),
                intent=intent,
            )
        query = intent_data.get("query") or payload.message

        # Scope the search to the most relevant item(s) by matching keywords from
        # the user's query against all saved item names / brands / doc titles.
        scoped_ids = [payload.item_id] if payload.item_id else _resolve_rag_items(query, db)

        try:
            chunks = rag.retrieve(query, item_ids=scoped_ids or None)
        except llm.LLMNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if not chunks:
            scope = "this item" if payload.item_id else ("these items" if scoped_ids else "your household")
            return ChatResponse(
                reply=(
                    f"I don't have any indexed manuals for {scope} yet. Find and save a "
                    "manual using the Add Item page, then ask again once it's indexed."
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

    # ── Discovery mode: only find_docs, no RAG ─────────────────────
    if payload.mode == "discovery":
        if intent != "find_docs":
            return ChatResponse(
                reply=(
                    "I can help find manuals, drivers, and accessories for your items. "
                    'Try: "find the manual for my Ninja CAFE Luxe3".'
                ),
                intent=intent,
            )
        return _handle_find_docs(intent_data, payload.message)

    # ── Full mode (item detail page): troubleshoot scoped to item ──
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
        if payload.item_id:
            return ChatResponse(
                reply=(
                    "I can answer questions about this item based on its saved manuals. "
                    'Try: "how to clean this", "why won\'t it turn on", or "how to replace the filter".'
                ),
                intent=intent,
            )
        return ChatResponse(
            reply=(
                "I can help find manuals, troubleshooting guides, drivers, and "
                'accessories. Try: "find the manual for my Canon GX1020 printer".'
            ),
            intent=intent,
        )

    return _handle_find_docs(intent_data, payload.message)


def _handle_find_docs(intent_data: dict, original_message: str) -> ChatResponse:
    product_name = intent_data.get("product_name") or " ".join(
        part for part in [intent_data.get("brand"), intent_data.get("model")] if part
    )

    # If the extracted product name is too short/meaningless (e.g. "LE"), fall back to
    # the user's original message for both the search query and the display name.
    if not product_name or len(product_name.strip()) < 4:
        product_name = original_message.strip()

    if not product_name or len(product_name.strip()) < 2:
        return ChatResponse(
            reply="Which product would you like documents for? Include the brand and model.",
            intent="find_docs",
        )

    # Build a focused search query: product + "owner manual PDF" is far more effective
    # at finding official manufacturer PDFs than the user's conversational message.
    search_query = f"{product_name} owner manual PDF official"
    raw_results = search_provider.search_with_fallback(search_query, max_results=12)
    if not raw_results:
        return ChatResponse(
            reply=f'I couldn\'t find anything online for "{product_name}". Try refining the brand/model.',
            intent="find_docs",
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
        intent="find_docs",
        documents=documents,
    )
