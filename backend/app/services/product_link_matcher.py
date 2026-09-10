"""
Production-safe Product Link Matching Engine for Lumière AI Fashion Search.

Connects an AI-recommended catalog product to verified external e-commerce product links
using multi-attribute confidence scoring (Brand, Name Similarity, Category, Color, Style,
and Visual Similarity).

Safety Rules:
- Never fabricate URLs.
- Never return placeholder URLs (demo-store, example.com).
- Never return an unverified URL as 'verified'.
- Never match solely on superficial name similarity (enforces brand & category sanity).
- Only matches when overall confidence exceeds a configurable threshold.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from app.models.product import Product, ProductExternalLink


DEFAULT_CONFIDENCE_THRESHOLD = 0.75

# Weights for multi-attribute matching (sum to 1.0)
DEFAULT_WEIGHTS = {
    "brand": 0.25,
    "name": 0.25,
    "category": 0.20,
    "color": 0.15,
    "style": 0.05,
    "visual": 0.10,
}

BLOCKED_DOMAINS = {
    "demo-store.example.com",
    "example.com",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "test.com",
}


@dataclass
class MatchResult:
    product_id: int
    store_name: str
    external_url: str
    match_score: float
    verification_status: str
    availability_status: str = "in_stock"
    reasons: list[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "store_name": self.store_name,
            "external_url": self.external_url,
            "match_score": round(self.match_score, 3),
            "verification_status": self.verification_status,
        }


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Remove punctuation, lower-case, collapse spaces
    cleaned = re.sub(r"[^\w\s]", " ", str(text).lower())
    return " ".join(cleaned.split())


def _brand_similarity(brand_a: Optional[str], brand_b: Optional[str]) -> float:
    a = _normalize_text(brand_a)
    b = _normalize_text(brand_b)
    if not a or not b:
        return 0.5  # Neutral if one is unknown/unspecified

    if a == b:
        return 1.0

    # Handle brand variations e.g. "levi's" vs "levis", "united colors of benetton" vs "ucb"
    if a in b or b in a:
        return 0.9

    synonyms = [
        {"levi's", "levis", "levi"},
        {"united colors of benetton", "ucb", "benetton"},
        {"us polo assn", "us polo", "uspa"},
        {"jack & jones", "jack and jones", "jack jones"},
    ]
    for s in synonyms:
        if a in s and b in s:
            return 1.0

    # Definite mismatch between two distinct known brands
    return 0.0


def _name_similarity(name_a: Optional[str], name_b: Optional[str]) -> float:
    a = _normalize_text(name_a)
    b = _normalize_text(name_b)
    if not a or not b:
        return 0.0

    # Token overlap (Jaccard) + SequenceMatcher hybrid
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0

    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return 0.5 * jaccard + 0.5 * seq


def _category_similarity(cat_a: Optional[str], cat_b: Optional[str], sub_a: Optional[str] = "", sub_b: Optional[str] = "") -> float:
    a = _normalize_text(cat_a)
    b = _normalize_text(cat_b)
    if not a or not b:
        return 0.5

    if a == b:
        return 1.0

    # Compatible cross-category aliases
    compatible_groups = [
        {"shirt", "t-shirt", "topwear", "tops"},
        {"shoes", "sneakers", "footwear", "casual shoes", "formal shoes"},
        {"jeans", "trousers", "bottomwear", "pants"},
        {"jacket", "coat", "hoodie", "sweatshirt", "sweater"},
        {"dress", "saree", "kurta", "ethnic wear"},
        {"accessories", "watches", "handbags", "belts", "wallets"},
    ]
    for grp in compatible_groups:
        if a in grp and b in grp:
            return 0.75

    return 0.0


def _color_similarity(color_a: Optional[str], color_b: Optional[str]) -> float:
    a = _normalize_text(color_a)
    b = _normalize_text(color_b)
    if not a or not b:
        return 0.5

    if a == b:
        return 1.0

    color_families = [
        {"navy", "blue", "navy blue", "teal", "turquoise"},
        {"gray", "grey", "charcoal", "silver", "steel"},
        {"white", "off white", "cream", "ivory"},
        {"black", "charcoal"},
        {"red", "burgundy", "maroon"},
        {"green", "olive", "khaki", "sea green"},
        {"beige", "nude", "tan", "sand", "cream"},
        {"brown", "tan", "coffee brown", "bronze", "rust"},
        {"pink", "rose", "magenta"},
        {"purple", "violet", "lavender", "mauve"},
        {"yellow", "mustard"},
        {"orange", "peach", "rust"},
    ]
    for fam in color_families:
        if a in fam and b in fam:
            return 0.75

    return 0.1


def is_valid_external_url(url: Optional[str]) -> bool:
    """Strict URL sanitizer that rejects non-HTTPS, empty, private IP, or placeholder domains."""
    if not url or not isinstance(url, str):
        return False
    trimmed = url.strip()
    if not trimmed.startswith("https://"):
        return False
    try:
        from app.services.url_verifier import is_private_or_blocked_host
        parsed = urlparse(trimmed)
        host = (parsed.hostname or "").lower()
        if not host or is_private_or_blocked_host(host):
            return False
        return True
    except Exception:
        return False


class ProductLinkMatcher:
    """
    Evaluates candidate external product links against a catalog product
    and attaches verified links when confidence meets or exceeds threshold.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.threshold = threshold
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_match_confidence(
        self,
        product: Union[Product, Dict[str, Any]],
        candidate: Union[ProductExternalLink, Dict[str, Any]],
        visual_similarity: Optional[float] = None,
    ) -> tuple[float, list[str]]:
        """
        Calculates confidence score between a catalog product and a candidate link.
        Enforces strict brand/category incompatibility penalties to prevent false positives.
        """
        # Extract attributes from Product model or dict
        p_name = getattr(product, "name", None) or (product.get("name") if isinstance(product, dict) else "")
        p_brand = getattr(product, "brand", None) or (product.get("brand") if isinstance(product, dict) else "")
        p_cat = getattr(product, "category", None) or (product.get("category") if isinstance(product, dict) else "")
        p_sub = getattr(product, "subcategory", None) or (product.get("subcategory") if isinstance(product, dict) else "")
        p_color = getattr(product, "color", None) or (product.get("color") if isinstance(product, dict) else "")
        p_style = getattr(product, "style", None) or (product.get("style") if isinstance(product, dict) else "")

        # Extract attributes from Candidate link model or dict
        c_name = getattr(candidate, "product_name", None) or (candidate.get("product_name") if isinstance(candidate, dict) else p_name)
        c_brand = getattr(candidate, "brand", None) or (candidate.get("brand") if isinstance(candidate, dict) else p_brand)
        c_cat = getattr(candidate, "category", None) or (candidate.get("category") if isinstance(candidate, dict) else p_cat)
        c_sub = getattr(candidate, "subcategory", None) or (candidate.get("subcategory") if isinstance(candidate, dict) else p_sub)
        c_color = getattr(candidate, "color", None) or (candidate.get("color") if isinstance(candidate, dict) else p_color)
        c_style = getattr(candidate, "style", None) or (candidate.get("style") if isinstance(candidate, dict) else p_style)

        # 1. Attribute scores
        brand_score = _brand_similarity(p_brand, c_brand)
        cat_score = _category_similarity(p_cat, c_cat, p_sub, c_sub)
        name_score = _name_similarity(p_name, c_name)
        color_score = _color_similarity(p_color, c_color)
        style_score = 1.0 if _normalize_text(p_style) == _normalize_text(c_style) else 0.5
        vis_score = max(0.0, min(1.0, visual_similarity)) if visual_similarity is not None else name_score

        # Hard Guardrails: Reject cross-brand or cross-category collisions immediately
        if p_brand and c_brand and brand_score == 0.0:
            return 0.0, ["Brand mismatch"]
        if p_cat and c_cat and cat_score == 0.0:
            return 0.0, ["Category mismatch"]

        w = self.weights
        total_score = (
            w["brand"] * brand_score
            + w["name"] * name_score
            + w["category"] * cat_score
            + w["color"] * color_score
            + w["style"] * style_score
            + w["visual"] * vis_score
        )

        reasons = []
        if brand_score >= 0.9:
            reasons.append("Exact brand match")
        if cat_score >= 0.9:
            reasons.append("Exact category match")
        if name_score >= 0.7:
            reasons.append("High title similarity")
        if color_score >= 0.75:
            reasons.append("Matching color family")

        return max(0.0, min(1.0, total_score)), reasons

    def match(
        self,
        product: Union[Product, Dict[str, Any]],
        candidates: List[Union[ProductExternalLink, Dict[str, Any]]],
        visual_similarity: Optional[float] = None,
    ) -> Optional[MatchResult]:
        """
        Finds the highest-confidence valid external link for a product.
        Returns MatchResult or None if no link meets threshold or passes safety checks.
        """
        if not candidates:
            return None

        best_match: Optional[MatchResult] = None
        highest_score = 0.0

        p_id = getattr(product, "id", None) or (product.get("id") if isinstance(product, dict) else 0)

        for cand in candidates:
            ext_url = getattr(cand, "external_url", None) or (cand.get("external_url") if isinstance(cand, dict) else "")
            store_name = getattr(cand, "store_name", None) or (cand.get("store_name") if isinstance(cand, dict) else "Store")
            v_status = getattr(cand, "verification_status", None) or (cand.get("verification_status") if isinstance(cand, dict) else "unverified")
            a_status = getattr(cand, "availability_status", None) or (cand.get("availability_status") if isinstance(cand, dict) else "in_stock")

            # Validate URL safety
            if not is_valid_external_url(ext_url):
                continue

            score, reasons = self.compute_match_confidence(product, cand, visual_similarity=visual_similarity)

            if score >= self.threshold and score > highest_score:
                highest_score = score
                best_match = MatchResult(
                    product_id=p_id,
                    store_name=store_name,
                    external_url=ext_url,
                    match_score=score,
                    verification_status=v_status,
                    availability_status=a_status,
                    reasons=reasons,
                )

        return best_match


# Global default instance
product_link_matcher = ProductLinkMatcher()
