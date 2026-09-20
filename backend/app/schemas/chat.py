from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    item_id: int | None = None
    mode: str = "full"  # "rag" | "discovery" | "full"


class DocumentSuggestion(BaseModel):
    doc_type: str
    title: str
    source_url: str
    reason: str | None = None


class Citation(BaseModel):
    title: str
    source_url: str


class ChatResponse(BaseModel):
    reply: str
    intent: str
    documents: list[DocumentSuggestion] = []
    citations: list[Citation] = []
