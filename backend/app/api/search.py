import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import SearchHistory, SearchResult, Recommendation
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.search import (
    DetectedAttributes,
    ImageSearchResponse,
    RecommendedProduct,
    ScoreBreakdown,
    SearchHistoryItem,
)
from app.services.ai_classifier import classify_image
from app.services.embedding import embedding_service
from app.services.recommendation import rank_products, score_product

router = APIRouter(prefix="/api/search", tags=["search"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _to_recommended(scored) -> RecommendedProduct:
    return RecommendedProduct(
        product=ProductResponse.model_validate(scored.product),
        scores=ScoreBreakdown(
            visual_score=scored.visual_score,
            category_score=scored.category_score,
            color_score=scored.color_score,
            style_score=scored.style_score,
            pattern_score=scored.pattern_score,
            budget_score=scored.budget_score,
            preference_score=scored.preference_score,
            overall_score=scored.overall_score,
            reasons=scored.reasons,
        ),
    )


@router.post("/image", response_model=ImageSearchResponse)
async def search_by_image(
    file: UploadFile = File(...),
    budget_min: float | None = None,
    budget_max: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use JPG, PNG, or WEBP.")

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Image exceeds the {settings.MAX_UPLOAD_MB}MB limit.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    image_path = upload_dir / filename
    with open(image_path, "wb") as f:
        f.write(contents)

    try:
        detected = classify_image(str(image_path))
    except NotImplementedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=422, detail="Could not analyze this image. Try a clearer photo.")

    primary = detected[0]
    query_embedding = embedding_service.generate_embedding(str(image_path))

    preferences = current_user.preferences
    preferred_styles = [s for s in (preferences.preferred_styles or "").split(",") if s]
    preferred_colors = [c for c in (preferences.preferred_colors or "").split(",") if c]
    effective_budget_min = budget_min if budget_min is not None else (preferences.budget_min or None)
    effective_budget_max = budget_max if budget_max is not None else (preferences.budget_max or None)

    catalog = db.query(Product).all()
    scored_all = [
        score_product(
            p,
            query_embedding,
            primary.category,
            primary.color,
            primary.style,
            primary.pattern,
            effective_budget_min,
            effective_budget_max,
            preferred_styles,
            preferred_colors,
        )
        for p in catalog
    ]

    best_matches = rank_products(scored_all, "best_match")[:8]

    affordable_pool = [s for s in scored_all if (s.product.discount_price or s.product.price) <= (effective_budget_max or 999999)]
    affordable = rank_products(affordable_pool or scored_all, "best_value")[:8]

    similar_pool = [s for s in scored_all if s.product.category == primary.category]
    similar_styles = rank_products(similar_pool, "similar_style")[8:16] or rank_products(similar_pool, "similar_style")[:8]

    top_match_product = best_matches[0].product if best_matches else None
    color_variants: list[Product] = []
    if top_match_product and top_match_product.group_key:
        color_variants = (
            db.query(Product)
            .filter(Product.group_key == top_match_product.group_key, Product.id != top_match_product.id)
            .all()
        )

    search = SearchHistory(
        user_id=current_user.id,
        image_path=str(image_path),
        detected_category=primary.category,
        detected_style=primary.style,
        detected_color=primary.color,
        confidence=primary.confidence,
        result_count=len(best_matches),
    )
    db.add(search)
    db.flush()

    for rank, s in enumerate(best_matches, start=1):
        db.add(SearchResult(search_id=search.id, product_id=s.product.id, similarity_score=s.visual_score, overall_score=s.overall_score, rank=rank))
        db.add(
            Recommendation(
                search_id=search.id,
                product_id=s.product.id,
                mode="best_match",
                visual_score=s.visual_score,
                category_score=s.category_score,
                color_score=s.color_score,
                style_score=s.style_score,
                pattern_score=s.pattern_score,
                budget_score=s.budget_score,
                preference_score=s.preference_score,
                overall_score=s.overall_score,
                reasons=json.dumps(s.reasons),
            )
        )
    db.commit()

    return ImageSearchResponse(
        search_id=search.id,
        ai_mode=settings.AI_MODE,
        detected_items=[
            DetectedAttributes(
                category=d.category,
                confidence=d.confidence,
                color=d.color,
                pattern=d.pattern,
                style=d.style,
                sleeve_type=d.sleeve_type,
                neckline=d.neckline,
                gender_category=d.gender_category,
                season=d.season,
            )
            for d in detected
        ],
        best_matches=[_to_recommended(s) for s in best_matches],
        affordable_alternatives=[_to_recommended(s) for s in affordable],
        similar_styles=[_to_recommended(s) for s in similar_styles],
        color_variants=[ProductResponse.model_validate(p) for p in color_variants],
    )


@router.get("/{search_id}", response_model=SearchHistoryItem)
def get_search(search_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    search = db.query(SearchHistory).filter(SearchHistory.id == search_id, SearchHistory.user_id == current_user.id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search


@router.delete("/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    search = db.query(SearchHistory).filter(SearchHistory.id == search_id, SearchHistory.user_id == current_user.id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    if search.image_path and os.path.exists(search.image_path):
        os.remove(search.image_path)
    db.delete(search)
    db.commit()
