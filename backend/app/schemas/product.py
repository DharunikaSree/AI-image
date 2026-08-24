from datetime import datetime

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    brand: str
    category: str
    subcategory: str
    style: str
    color: str
    pattern: str
    price: float
    discount_price: float | None
    currency: str
    image_url: str
    product_url: str
    platform: str
    availability: bool
    group_key: str

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    brand: str = ""
    category: str
    subcategory: str = ""
    style: str = ""
    color: str = ""
    pattern: str = "Solid"
    price: float = 0
    discount_price: float | None = None
    currency: str = "INR"
    image_url: str = ""
    product_url: str = ""
    platform: str = "Demo Store"
    availability: bool = True
    group_key: str = ""


class ProductUpdate(ProductCreate):
    pass
