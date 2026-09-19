from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentSelectItem(BaseModel):
    doc_type: str
    title: str
    source_url: str


class DocumentSelectRequest(BaseModel):
    item_id: int
    documents: list[DocumentSelectItem]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    doc_type: str
    title: str
    source_url: str
    local_path: str | None
    indexed_status: str
    selected_at: datetime
