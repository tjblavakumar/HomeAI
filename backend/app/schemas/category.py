from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: str
    is_custom: bool
    item_count: int = 0


class CategoryCreate(BaseModel):
    name: str
    icon: str = ""
