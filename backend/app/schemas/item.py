from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemFromUrl(BaseModel):
    """Create an item + download and index a manual from a direct URL."""
    url: str
    name: str
    category_id: int
    brand: str | None = None
    model_number: str | None = None


class ItemCreate(BaseModel):
    name: str
    brand: str | None = None
    model_number: str | None = None
    category_id: int
    purchase_store: str | None = None
    purchase_date: str | None = None
    notes: str | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str | None
    model_number: str | None
    category_id: int
    purchase_store: str | None
    purchase_date: str | None
    photo_path: str | None
    notes: str | None
    created_at: datetime
