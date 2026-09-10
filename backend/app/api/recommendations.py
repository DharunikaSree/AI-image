import os
from fastapi import APIRouter, Depends, HTTPException, Query
import numpy as np
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.activity import SearchHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.search import RecommendedProduct, ScoreBreakdown
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

    query_embedding = np.zeros(512, dtype=np.float32)
    visual_scores_by_id: dict[int, float] = {}

    # 1. Generate CLIP embedding from the original search image and query FAISS
    if search.image_path and os.path.exists(search.image_path):
        query_embedding = embedding_service.generate_embedding(search.image_path)
        faiss_matches = embedding_service.search_faiss(query_embedding, top_k=80)
        visual_scores_by_id = {pid: score for pid, score in faiss_matches}

    # 2. Fallback to stored search results if FAISS returned no matches or image was moved
    if not visual_scores_by_id and search.results:
        visual_scores_by_id = {sr.product_id: (sr.similarity_score / 100.0) for sr in search.results}

    candidate_pids = list(visual_scores_by_id.keys())
    if candidate_pids:
        candidates = db.query(Product).filter(Product.id.in_(candidate_pids)).all()
    else:
        candidates = db.query(Product).filter(Product.category == search.detected_category).limit(80).all()
        if not candidates:
            candidates = db.query(Product).limit(80).all()

    preferences = current_user.preferences
    preferred_styles = [s for s in (preferences.preferred_styles or "").split(",") if s] if preferences else []
    preferred_colors = [c for c in (preferences.preferred_colors or "").split(",") if c] if preferences else []
    budget_min = preferences.budget_min if preferences else None
    budget_max = preferences.budget_max if preferences else None

    scored = [
        score_product(
            p,
            query_embedding,
            search.detected_category,
            search.detected_color,
            search.detected_style,
            "Solid",
            budget_min,
            budget_max,
            preferred_styles,
            preferred_colors,
            visual_similarity_score=visual_scores_by_id.get(p.id),
        )
        for p in candidates
    ]

    if mode == "similar_style":
        similar_pool = [s for s in scored if s.product.category.lower() == search.detected_category.lower()]
        ranked = rank_products(similar_pool or scored, "similar_style")[:12]
    elif mode == "best_value":
        affordable_pool = [s for s in scored if (s.product.discount_price or s.product.price) <= (budget_max or 999999)]
        ranked = rank_products(affordable_pool or scored, "best_value")[:12]
    else:
        ranked = rank_products(scored, mode)[:12]

    from app.services.shopping_destination_resolver import destination_resolver

    results = []
    for s in ranked:
        prod_resp = ProductResponse.model_validate(s.product)
        dest = destination_resolver.resolve(prod_resp)

        results.append(
            RecommendedProduct(
                product=prod_resp,
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
                store_name=dest.store_name,
                store_url=dest.store_url,
                store_available=dest.store_available,
                destination_type=dest.destination_type,
                store_cta=dest.store_cta,
            )
        )

    return results

