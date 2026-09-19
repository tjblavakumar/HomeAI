from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category

STARTER_CATEGORIES = [
    ("Electronics", "device"),
    ("Appliances", "blender"),
    ("Furniture", "chair"),
    ("Tools", "wrench"),
    ("Other", "box"),
]


def seed_categories(db: Session) -> None:
    existing_names = set(db.execute(select(Category.name)).scalars())
    for name, icon in STARTER_CATEGORIES:
        if name not in existing_names:
            db.add(Category(name=name, icon=icon, is_custom=False))
    db.commit()
