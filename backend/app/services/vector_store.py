from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

COLLECTION_NAME = "manuals"

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_manuals_collection():
    # No embedding_function: we always pass precomputed OpenAI embeddings ourselves.
    return get_chroma_client().get_or_create_collection(name=COLLECTION_NAME)
