import math
import os
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import SearchHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import PaginatedProductResponse, ProductCreate, ProductResponse, ProductUpdate
from app.services.embedding import embedding_service

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0
    avg_confidence = db.query(func.avg(SearchHistory.confidence)).scalar() or 0

    # Limit search aggregation to the most recent searches for performance
    searches = db.query(SearchHistory).order_by(SearchHistory.id.desc()).limit(1000).all()
    category_counts = Counter(s.detected_category for s in searches if s.detected_category)
    color_counts = Counter(s.detected_color for s in searches if s.detected_color)

    by_day: Counter = Counter()
    for s in searches:
        by_day[s.created_at.strftime("%Y-%m-%d")] += 1

    # Database-level price distribution aggregation without loading rows into Python RAM
    effective_price = func.coalesce(Product.discount_price, Product.price)
    price_case = case(
        (effective_price < 500, "Under ₹500"),
        (effective_price < 1000, "₹500-1000"),
        (effective_price < 2000, "₹1000-2000"),
        (effective_price < 5000, "₹2000-5000"),
        else_="₹5000+",
    ).label("price_range")

    price_rows = db.query(price_case, func.count(Product.id)).group_by(price_case).all()
    price_map = {row[0]: row[1] for row in price_rows if row[0]}
    ordered_ranges = ["Under ₹500", "₹500-1000", "₹1000-2000", "₹2000-5000", "₹5000+"]
    price_distribution = [{"range": r, "count": price_map.get(r, 0)} for r in ordered_ranges]

    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_searches": total_searches,
        "average_confidence": round(avg_confidence, 1),
        "searches_per_day": [{"date": k, "count": v} for k, v in sorted(by_day.items())],
        "top_categories": [{"category": k, "count": v} for k, v in category_counts.most_common(8)],
        "popular_colors": [{"color": k, "count": v} for k, v in color_counts.most_common(8)],
        "price_distribution": price_distribution,
    }


@router.get("/products", response_model=PaginatedProductResponse)
def admin_list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category: str | None = None,
    sort_by: str = Query("id", pattern="^(id|name|price|category|brand)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    query = db.query(Product)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.category.ilike(term),
                Product.description.ilike(term),
            )
        )

    if category and category.strip() and category.lower() != "all":
        query = query.filter(Product.category == category.strip())

    total = query.count()

    sort_col = getattr(Product, sort_by, Product.id)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()
    total_pages = math.ceil(total / limit) if total > 0 else 1

    return PaginatedProductResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for k, v in payload.model_dump().items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()


@router.post("/products/{product_id}/embedding")
def generate_embedding_for_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.image_url:
        raise HTTPException(status_code=400, detail="Product does not have an image_url configured")

    # Locate image on disk
    filename = Path(product.image_url).name
    img_path = None
    for d in settings.dataset_image_dirs:
        if (d / filename).exists():
            img_path = str(d / filename)
            break
    if not img_path and os.path.exists("." + product.image_url):
        img_path = "." + product.image_url

    if not img_path:
        raise HTTPException(status_code=400, detail="Image file not found on disk")

    try:
        vec = embedding_service.generate_embedding(img_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {e}")

    product.embedding_reference = embedding_service.to_string(vec)
    db.commit()
    return {"status": "embedding_generated", "product_id": product_id}
