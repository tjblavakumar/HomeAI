from __future__ import annotations

from app.services import llm
from app.services.vector_store import get_manuals_collection

TOP_K = 10

ANSWER_SYSTEM_PROMPT = """You are a household troubleshooting assistant. Answer the user's \
question using ONLY the numbered excerpts from their saved manuals below. Cite excerpts \
inline like [1], [2] matching their number. Be thorough — read through ALL excerpts \
carefully. If the excerpts together don't contain the answer, say you don't have that \
information in the saved manuals instead of guessing."""


def retrieve(
    query: str,
    item_id: int | None = None,
    top_k: int = TOP_K,
    item_ids: list[int] | None = None,
) -> list[dict]:
    embedding = llm.embed_texts([query])[0]
    collection = get_manuals_collection()

    where = None
    if item_ids:
        where = {"item_id": {"$in": item_ids}}
    elif item_id is not None:
        where = {"item_id": item_id}

    results = collection.query(query_embeddings=[embedding], n_results=top_k, where=where)

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    chunks = []
    for text, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
        chunks.append({"text": text, "metadata": metadata, "distance": distance})
    return chunks


def generate_answer(query: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[{i}] {chunk['text']}" for i, chunk in enumerate(chunks, start=1))
    user_content = f"Question: {query}\n\nExcerpts from saved manuals:\n{context}"
    return llm.chat_completion(
        [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
