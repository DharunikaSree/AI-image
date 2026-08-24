from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.activity import Favorite, SearchHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.search import SearchHistoryItem
from app.schemas.user import PreferencesResponse, PreferencesUpdate

router = APIRouter(prefix="/api", tags=["user"])


# ---------- Favorites ----------

@router.post("/favorites/{product_id}", status_code=201)
def add_favorite(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Product not found")
    existing = db.query(Favorite).filter(Favorite.user_id == current_user.id, Favorite.product_id == product_id).first()
    if existing:
        return {"status": "already_favorited"}
    db.add(Favorite(user_id=current_user.id, product_id=product_id))
    db.commit()
    return {"status": "added"}


@router.get("/favorites", response_model=list[ProductResponse])
def list_favorites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Product).join(Favorite, Favorite.product_id == Product.id).filter(Favorite.user_id == current_user.id).all()
    return rows


@router.delete("/favorites/{product_id}", status_code=204)
def remove_favorite(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    fav = db.query(Favorite).filter(Favorite.user_id == current_user.id, Favorite.product_id == product_id).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()


# ---------- History ----------

@router.get("/history", response_model=list[SearchHistoryItem])
def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .all()
    )


@router.delete("/history/{history_id}", status_code=204)
def delete_history(history_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(SearchHistory).filter(SearchHistory.id == history_id, SearchHistory.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")
    db.delete(item)
    db.commit()


# ---------- Profile / Preferences ----------

@router.get("/profile", response_model=PreferencesResponse)
def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = current_user.preferences
    return PreferencesResponse(
        preferred_styles=[s for s in (p.preferred_styles or "").split(",") if s],
        preferred_colors=[c for c in (p.preferred_colors or "").split(",") if c],
        preferred_categories=[c for c in (p.preferred_categories or "").split(",") if c],
        budget_min=p.budget_min,
        budget_max=p.budget_max,
    )


@router.put("/profile", response_model=PreferencesResponse)
def update_profile(payload: PreferencesUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = current_user.preferences
    p.preferred_styles = ",".join(payload.preferred_styles)
    p.preferred_colors = ",".join(payload.preferred_colors)
    p.preferred_categories = ",".join(payload.preferred_categories)
    p.budget_min = payload.budget_min
    p.budget_max = payload.budget_max
    db.commit()
    return payload
