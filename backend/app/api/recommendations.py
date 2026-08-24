from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.activity import SearchHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.search import RecommendedProduct, ScoreBreakdown
from app.services.ai_classifier import classify_image
from app.services.embedding import embedding_service
from app.services.recommendation import rank_products, score_product

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/{search_id}", response_model=list[RecommendedProduct])
def get_recommendations(
    search_id: int,
    mode: str = Query("best_match", pattern="^(best_match|best_value|lowest_price|premium|similar_style)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    search = db.query(SearchHistory).filter(SearchHistory.id == search_id, SearchHistory.user_id == current_user.id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    query_embedding = embedding_service.generate_embedding(search.image_path)
    preferences = current_user.preferences
    preferred_styles = [s for s in (preferences.preferred_styles or "").split(",") if s]
    preferred_colors = [c for c in (preferences.preferred_colors or "").split(",") if c]

    catalog = db.query(Product).all()
    scored = [
        score_product(
            p,
            query_embedding,
            search.detected_category,
            search.detected_color,
            search.detected_style,
            "Solid",
            preferences.budget_min,
            preferences.budget_max,
            preferred_styles,
            preferred_colors,
        )
        for p in catalog
    ]
    ranked = rank_products(scored, mode)[:12]
    return [
        RecommendedProduct(
            product=ProductResponse.model_validate(s.product),
            scores=ScoreBreakdown(
                visual_score=s.visual_score,
                category_score=s.category_score,
                color_score=s.color_score,
                style_score=s.style_score,
                pattern_score=s.pattern_score,
                budget_score=s.budget_score,
                preference_score=s.preference_score,
                overall_score=s.overall_score,
                reasons=s.reasons,
            ),
        )
        for s in ranked
    ]
