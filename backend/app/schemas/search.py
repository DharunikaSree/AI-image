from datetime import datetime

from pydantic import BaseModel

from app.schemas.product import ProductResponse


class DetectedAttributes(BaseModel):
    category: str
    confidence: float
    color: str
    pattern: str
    style: str
    sleeve_type: str | None = None
    neckline: str | None = None
    gender_category: str | None = None
    season: str | None = None


class ScoreBreakdown(BaseModel):
    visual_score: float
    category_score: float
    color_score: float
    style_score: float
    pattern_score: float
    budget_score: float
    preference_score: float
    overall_score: float
    reasons: list[str]


class RecommendedProduct(BaseModel):
    product: ProductResponse
    scores: ScoreBreakdown


class ImageSearchResponse(BaseModel):
    search_id: int
    ai_mode: str
    detected_items: list[DetectedAttributes]
    best_matches: list[RecommendedProduct]
    affordable_alternatives: list[RecommendedProduct]
    similar_styles: list[RecommendedProduct]
    color_variants: list[ProductResponse]
    outfit: list[RecommendedProduct] | None = None
    outfit_total_price: float | None = None


class SearchHistoryItem(BaseModel):
    id: int
    image_path: str
    detected_category: str
    detected_style: str
    detected_color: str
    confidence: float
    result_count: int
    created_at: datetime

    class Config:
        from_attributes = True
