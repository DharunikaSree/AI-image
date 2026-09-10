from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.schemas.product import ProductResponse

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    category: str | None = None,
    gender: str | None = None,
    color: str | None = None,
    style: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
):
    q = db.query(Product)
    if category:
        if category.lower() in ["shoes", "sneakers"]:
            q = q.filter(Product.category.in_(["Shoes", "Sneakers"]))
        else:
            q = q.filter(Product.category == category)
    if gender:
        g = gender.strip().lower()
        if g in ["men", "boys"]:
            q = q.filter(Product.name.ilike("%Men%") | Product.name.ilike("%Boys%"))
        elif g in ["women", "girls"]:
            q = q.filter(Product.name.ilike("%Women%") | Product.name.ilike("%Girls%"))
    if color:
        q = q.filter(Product.color == color)
    if style:
        q = q.filter(Product.style == style)
    if min_price is not None:
        q = q.filter(func.coalesce(Product.discount_price, Product.price) >= min_price)
    if max_price is not None:
        q = q.filter(func.coalesce(Product.discount_price, Product.price) <= max_price)
    return q.offset((page - 1) * page_size).limit(page_size).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/variants", response_model=list[ProductResponse])
def get_color_variants(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.group_key:
        return []
    return db.query(Product).filter(Product.group_key == product.group_key, Product.id != product.id).all()
