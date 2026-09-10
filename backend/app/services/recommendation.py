"""
Transparent, configurable recommendation scoring engine.

Weights live in app.core.recommendation_config.RECOMMENDATION_WEIGHTS so
they can be tuned without touching this file. Every score returned to the
frontend includes a breakdown + human-readable reasons ("Why we recommend
this"), never just a single opaque percentage.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.recommendation_config import RECOMMENDATION_WEIGHTS
from app.models.product import Product
from app.services.embedding import embedding_service, cosine_similarity


@dataclass
class ScoredProduct:
    product: Product
    visual_score: float
    category_score: float
    color_score: float
    style_score: float
    pattern_score: float
    budget_score: float
    preference_score: float
    overall_score: float
    reasons: list[str]


def _budget_score(price: float, budget_min: float | None, budget_max: float | None) -> float:
    if budget_min is None and budget_max is None:
        return 0.7  # neutral score when user gave no budget context
    lo = budget_min or 0
    hi = budget_max if budget_max is not None else price * 10
    if lo <= price <= hi:
        return 1.0
    if price < lo:
        return max(0.4, 1 - (lo - price) / max(lo, 1))
    overshoot = (price - hi) / max(hi, 1)
    return max(0.0, 1 - overshoot)


def score_product(
    product: Product,
    query_embedding: np.ndarray,
    detected_category: str,
    detected_color: str,
    detected_style: str,
    detected_pattern: str,
    budget_min: float | None,
    budget_max: float | None,
    preferred_styles: list[str],
    preferred_colors: list[str],
    visual_similarity_score: float | None = None,
) -> ScoredProduct:
    if visual_similarity_score is not None:
        visual = max(0.0, min(1.0, visual_similarity_score))
    else:
        product_embedding = embedding_service.from_string(product.embedding_reference)
        visual = max(0.0, cosine_similarity(query_embedding, product_embedding))

    category_score = 1.0 if product.category.lower() == detected_category.lower() else 0.25
    color_score = 1.0 if product.color.lower() == detected_color.lower() else 0.3
    style_score = 1.0 if product.style.lower() == detected_style.lower() else 0.35
    pattern_score = 1.0 if product.pattern.lower() == detected_pattern.lower() else 0.5
    budget = _budget_score(product.discount_price or product.price, budget_min, budget_max)

    preference_hits = 0
    preference_total = 0
    if preferred_styles:
        preference_total += 1
        if product.style in preferred_styles:
            preference_hits += 1
    if preferred_colors:
        preference_total += 1
        if product.color in preferred_colors:
            preference_hits += 1
    preference_score = (preference_hits / preference_total) if preference_total else 0.5

    w = RECOMMENDATION_WEIGHTS
    overall = (
        visual * w["visual_similarity"]
        + category_score * w["category_match"]
        + color_score * w["color_match"]
        + style_score * w["style_match"]
        + pattern_score * w["pattern_match"]
        + budget * w["budget_compatibility"]
        + preference_score * w["user_preference"]
    )

    reasons = []
    if category_score >= 1.0:
        reasons.append("Same clothing category")
    if color_score >= 1.0:
        reasons.append("Very similar color")
    if style_score >= 1.0:
        reasons.append("Similar style")
    if visual >= 0.75:
        reasons.append("Strong visual match")
    if budget >= 0.9:
        reasons.append("Within your budget")
    if preference_hits > 0:
        reasons.append("Matches your saved preferences")
    if not reasons:
        reasons.append("Related item from catalog")

    return ScoredProduct(
        product=product,
        visual_score=round(visual * 100, 1),
        category_score=round(category_score * 100, 1),
        color_score=round(color_score * 100, 1),
        style_score=round(style_score * 100, 1),
        pattern_score=round(pattern_score * 100, 1),
        budget_score=round(budget * 100, 1),
        preference_score=round(preference_score * 100, 1),
        overall_score=round(overall * 100, 1),
        reasons=reasons,
    )


def rank_products(scored: list[ScoredProduct], mode: str = "best_match") -> list[ScoredProduct]:
    if mode == "lowest_price":
        return sorted(scored, key=lambda s: (s.product.discount_price or s.product.price))
    if mode == "best_value":
        # balances similarity with affordability, per spec: never just "cheapest"
        return sorted(
            scored,
            key=lambda s: -(0.6 * s.overall_score - 0.4 * (s.product.discount_price or s.product.price) / 100),
        )
    if mode == "premium":
        return sorted(scored, key=lambda s: -(s.product.discount_price or s.product.price))
    # best_match / similar_style default
    return sorted(scored, key=lambda s: -s.overall_score)
