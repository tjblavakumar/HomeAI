from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Item
from app.schemas import ItemCreate, ItemOut, ScanResult
from app.services import ocr

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_db)) -> list[Item]:
    return list(db.execute(select(Item)).scalars())


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
