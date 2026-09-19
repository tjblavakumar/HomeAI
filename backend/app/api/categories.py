from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Item
from app.schemas import CategoryCreate, CategoryOut, ItemOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.execute(
        select(Category, func.count(Item.id))
        .outerjoin(Item, Item.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.id)
    ).all()
    return [
        CategoryOut(
            id=category.id,
            name=category.name,
            icon=category.icon,
            is_custom=category.is_custom,
            item_count=count,
        )
        for category, count in rows
    ]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> Category:
    existing = db.execute(select(Category).where(Category.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    category = Category(name=payload.name, icon=payload.icon, is_custom=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}/items", response_model=list[ItemOut])
def list_items_in_category(category_id: int, db: Session = Depends(get_db)) -> list[Item]:
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return list(db.execute(select(Item).where(Item.category_id == category_id)).scalars())
