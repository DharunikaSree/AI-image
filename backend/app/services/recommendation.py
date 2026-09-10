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
    detected_gender: str | None = None,
) -> ScoredProduct:
    if visual_similarity_score is not None:
        visual = max(0.0, min(1.0, visual_similarity_score))
    else:
        product_embedding = embedding_service.from_string(product.embedding_reference)
        visual = max(0.0, cosine_similarity(query_embedding, product_embedding))

    p_cat = (product.category or "").lower()
    d_cat = (detected_category or "").lower()
    if p_cat == d_cat:
        category_score = 1.0
    elif (p_cat in ["shoes", "sneakers"] and d_cat in ["shoes", "sneakers"]) or \
         (p_cat in ["jacket", "hoodie", "sweater"] and d_cat in ["jacket", "hoodie", "sweater"]) or \
         (p_cat in ["shirt", "t-shirt"] and d_cat in ["shirt", "t-shirt"]) or \
         (p_cat in ["trousers", "jeans"] and d_cat in ["trousers", "jeans"]):
        category_score = 0.85
    else:
        category_score = 0.15

    color_score = 1.0 if (product.color or "").lower() == (detected_color or "").lower() else 0.3
    style_score = 1.0 if (product.style or "").lower() == (detected_style or "").lower() else 0.35
    pattern_score = 1.0 if (product.pattern or "").lower() == (detected_pattern or "").lower() else 0.5
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

    # Gender compatibility factor
    gender_factor = 1.0
    if detected_gender:
        g = detected_gender.strip().lower()
        p_name = (product.name or "").lower()
        p_desc = (product.description or "").lower()
        if g in ["men", "boys"]:
            if "women" in p_name or "women" in p_desc or "girls" in p_name or "ladies" in p_name:
                gender_factor = 0.3  # heavy penalty against showing women's dresses/shoes for men's searches
            elif "men" in p_name or "boys" in p_name or "gents" in p_name:
                gender_factor = 1.15
        elif g in ["women", "girls"]:
            p_words = p_name.split()
            if "men" in p_words or "boys" in p_name or "gents" in p_name:
                gender_factor = 0.3
            elif "women" in p_name or "girls" in p_name or "ladies" in p_name:
                gender_factor = 1.15

    w = RECOMMENDATION_WEIGHTS
    base_overall = (
        visual * w["visual_similarity"]
        + category_score * w["category_match"]
        + color_score * w["color_match"]
        + style_score * w["style_match"]
        + pattern_score * w["pattern_match"]
        + budget * w["budget_compatibility"]
        + preference_score * w["user_preference"]
    )

    overall = min(1.0, base_overall * gender_factor)

    reasons = []
    if category_score >= 0.85:
        reasons.append("Same clothing category" if category_score == 1.0 else "Matching clothing category")
    if color_score >= 1.0:
        reasons.append("Very similar color")
    if style_score >= 1.0:
        reasons.append("Similar style")
    if visual >= 0.75:
        reasons.append("Strong visual match")
    if budget >= 0.9:
        reasons.append("Within your budget")
    if gender_factor > 1.0 and detected_gender:
        reasons.append(f"Tailored for {detected_gender.title()}")
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
