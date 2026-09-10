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


class ShoppingDestinationResponse(BaseModel):
    store_name: str
    store_url: str
    store_available: bool
    destination_type: str  # "exact_product" | "official_store" | "shopping_search" | "fallback_search"
    store_cta: str         # "Shop Now" | "Shop Brand" | "Find Similar Products" | "Search Online"
    is_exact_match: bool = False
    query_terms: str = ""


class RecommendedProduct(BaseModel):
    product: ProductResponse
    scores: ScoreBreakdown
    store_name: str | None = None
    store_url: str | None = None
    store_available: bool = False
    destination_type: str = "fallback_search"
    store_cta: str = "Search Online"
    shopping_destination: ShoppingDestinationResponse | None = None



class MultiItemResult(BaseModel):
    item_id: int
    crop_filename: str
    crop_preview_url: str | None = None
    detected_attributes: DetectedAttributes
    best_matches: list[RecommendedProduct]
    affordable_alternatives: list[RecommendedProduct]
    similar_styles: list[RecommendedProduct]
    color_variants: list[ProductResponse]


class ImageSearchResponse(BaseModel):
    search_id: int
    ai_mode: str
    image_path: str | None = None
    query_image_url: str | None = None
    detected_items: list[DetectedAttributes]
    best_matches: list[RecommendedProduct]
    affordable_alternatives: list[RecommendedProduct]
    similar_styles: list[RecommendedProduct]
    color_variants: list[ProductResponse]
    outfit: list[RecommendedProduct] | None = None
    outfit_total_price: float | None = None
    items: list[MultiItemResult] | None = None


class MultiItemSearchResponse(BaseModel):
    search_id: int
    ai_mode: str
    image_path: str | None = None
    query_image_url: str | None = None
    total_items: int
    items: list[MultiItemResult]
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
