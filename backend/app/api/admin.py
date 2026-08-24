from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.activity import SearchHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.embedding import embedding_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0
    avg_confidence = db.query(func.avg(SearchHistory.confidence)).scalar() or 0

    searches = db.query(SearchHistory).all()
    category_counts = Counter(s.detected_category for s in searches if s.detected_category)
    color_counts = Counter(s.detected_color for s in searches if s.detected_color)

    by_day: Counter = Counter()
    for s in searches:
        by_day[s.created_at.strftime("%Y-%m-%d")] += 1

    products = db.query(Product).all()
    price_buckets = Counter()
    for p in products:
        price = p.discount_price or p.price
        if price < 500:
            price_buckets["Under ₹500"] += 1
        elif price < 1000:
            price_buckets["₹500-1000"] += 1
        elif price < 2000:
            price_buckets["₹1000-2000"] += 1
        elif price < 5000:
            price_buckets["₹2000-5000"] += 1
        else:
            price_buckets["₹5000+"] += 1

    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_searches": total_searches,
        "average_confidence": round(avg_confidence, 1),
        "searches_per_day": [{"date": k, "count": v} for k, v in sorted(by_day.items())],
        "top_categories": [{"category": k, "count": v} for k, v in category_counts.most_common(8)],
        "popular_colors": [{"color": k, "count": v} for k, v in color_counts.most_common(8)],
        "price_distribution": [{"range": k, "count": v} for k, v in price_buckets.items()],
    }


@router.get("/products", response_model=list[ProductResponse])
def admin_list_products(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return db.query(Product).order_by(Product.id.desc()).all()


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
    if not product.image_url or not product.image_url.startswith("/"):
        raise HTTPException(status_code=400, detail="Product needs a local image_url (served from /uploads) to embed")
    try:
        vec = embedding_service.generate_embedding("." + product.image_url)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Image file not found on disk")
    product.embedding_reference = embedding_service.to_string(vec)
    db.commit()
    return {"status": "embedding_generated", "product_id": product_id}
