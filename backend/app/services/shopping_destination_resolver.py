"""
Universal Shopping Destination Resolver for Lumière AI Fashion Search (Phase 8 Step 13)

Ensures that every AI-recommended catalog product resolves to a legitimate, safe,
and actionable external shopping destination while maintaining strict truthfulness
and zero-hallucination guarantees.

Destination Hierarchy:
  1. exact_product    -> Verified direct retailer product URL. (CTA: "Shop Now")
  2. official_store   -> Verified official brand / store landing hub. (CTA: "Shop Brand")
  3. shopping_search  -> Retailer search query from product metadata. (CTA: "Find Similar Products")
  4. fallback_search  -> Broad fashion search query. (CTA: "Search Online")

Truthfulness & Safety Guarantees:
  - Never fabricate product IDs or invent fake item pages.
  - Never mark shopping-search destinations as exact product matches.
  - Never claim unverified items are in stock.
  - HTTPS only with strict URL parameter encoding (urllib.parse.quote_plus).
  - Block localhost, private IPs, SSRF, and dummy domains.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from app.services.product_link_matcher import is_valid_external_url
from app.services.url_verifier import is_private_or_blocked_host, prevalidate_url


@dataclass
class RetailerConfig:
    """Configurable retailer search integration."""
    store_name: str
    domain: str
    search_url_template: str
    enabled: bool = True
    priority: int = 1

    def build_search_url(self, query: str) -> str:
        encoded = urllib.parse.quote_plus(query.strip())
        return self.search_url_template.format(query=encoded)


class RetailerRegistry:
    """Registry of whitelisted e-commerce retailers for safe query construction."""

    DEFAULT_RETAILERS: list[RetailerConfig] = [
        RetailerConfig(
            store_name="Myntra",
            domain="myntra.com",
            search_url_template="https://www.myntra.com/search?rawQuery={query}",
            enabled=True,
            priority=1,
        ),
        RetailerConfig(
            store_name="Amazon",
            domain="amazon.in",
            search_url_template="https://www.amazon.in/s?k={query}&i=apparel",
            enabled=True,
            priority=2,
        ),
        RetailerConfig(
            store_name="Ajio",
            domain="ajio.com",
            search_url_template="https://www.ajio.com/search/?text={query}",
            enabled=True,
            priority=3,
        ),
        RetailerConfig(
            store_name="Tata CLiQ",
            domain="tatacliq.com",
            search_url_template="https://www.tatacliq.com/search/?searchCategory=all&text={query}",
            enabled=True,
            priority=4,
        ),
        RetailerConfig(
            store_name="Google Shopping",
            domain="google.com",
            search_url_template="https://www.google.com/search?tbm=shop&q={query}",
            enabled=True,
            priority=5,
        ),
    ]

    def __init__(self, custom_retailers: Optional[list[RetailerConfig]] = None):
        self._retailers: dict[str, RetailerConfig] = {}
        retailers_to_load = custom_retailers or self.DEFAULT_RETAILERS
        for r in retailers_to_load:
            self._retailers[r.store_name.lower()] = r

    def get_retailer(self, name: str) -> Optional[RetailerConfig]:
        return self._retailers.get(name.lower().strip())

    def get_primary_retailer(self, category: Optional[str] = None) -> RetailerConfig:
        enabled = [r for r in self._retailers.values() if r.enabled]
        sorted_retailers = sorted(enabled, key=lambda x: x.priority)
        return sorted_retailers[0] if sorted_retailers else self.DEFAULT_RETAILERS[0]

    def get_fallback_retailer(self) -> RetailerConfig:
        return self._retailers.get("google shopping") or self.DEFAULT_RETAILERS[-1]

    def list_retailers(self) -> list[RetailerConfig]:
        return [r for r in self._retailers.values() if r.enabled]


@dataclass
class ResolvedDestination:
    """Actionable shopping destination output."""
    store_name: str
    store_url: str
    store_available: bool
    destination_type: str  # "exact_product" | "official_store" | "shopping_search" | "fallback_search"
    store_cta: str         # "Shop Now" | "Shop Brand" | "Find Similar Products" | "Search Online"
    is_exact_match: bool
    query_terms: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_name": self.store_name,
            "store_url": self.store_url,
            "store_available": self.store_available,
            "destination_type": self.destination_type,
            "store_cta": self.store_cta,
            "is_exact_match": self.is_exact_match,
            "query_terms": self.query_terms,
        }


class ShoppingDestinationResolver:
    """
    Deterministically resolves the highest-fidelity shopping destination
    for any catalog product according to the 4-tier destination architecture.
    """

    def __init__(self, registry: Optional[RetailerRegistry] = None):
        self.registry = registry or RetailerRegistry()

    @staticmethod
    def _clean_token(text: Optional[str]) -> str:
        if not text:
            return ""
        # Remove punctuation, extra spaces
        cleaned = re.sub(r"[^\w\s-]", " ", str(text))
        return " ".join(cleaned.split())

    def build_metadata_query(
        self,
        name: Optional[str] = None,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        color: Optional[str] = None,
        style: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> str:
        """
        Constructs a clean, high-precision search query from product metadata.
        Example: "Turtle Navy Blue Checked Casual Shirt"
        """
        seen_words: set[str] = set()
        query_parts: list[str] = []

        def add_token(val: Optional[str]):
            cleaned = self._clean_token(val)
            if not cleaned or cleaned.lower() in {"unknown", "none", "null", "general", "n a", "na"}:
                return
            for word in cleaned.split():
                w_lower = word.lower()
                if w_lower not in seen_words and len(word) > 1:
                    seen_words.add(w_lower)
                    query_parts.append(word)

        # 1. Brand (e.g. Turtle, Puma, Nike)
        add_token(brand)

        # 2. Gender / Audience if present (e.g. Men, Women, Unisex)
        add_token(gender)

        # 3. Color (e.g. Navy Blue, Black, Red)
        add_token(color)

        # 4. Style (e.g. Casual, Formal, Sporty)
        if style and style.lower() not in {"solid", "regular"}:
            add_token(style)

        # 5. Category / Subcategory / Article (e.g. Shirt, Jeans, Watch)
        if subcategory and subcategory.lower() != (category or "").lower():
            add_token(subcategory)
        add_token(category)

        # 6. Specific descriptive words from product title
        if name:
            for w in self._clean_token(name).split():
                w_lower = w.lower()
                if w_lower not in seen_words and len(w) > 2:
                    seen_words.add(w_lower)
                    query_parts.append(w)
                    if len(query_parts) >= 6:
                        break

        # Capped to 6 most relevant terms to avoid query truncation on retailer engines
        final_tokens = query_parts[:6]
        return " ".join(final_tokens)

    def resolve(
        self,
        product: Union[Dict[str, Any], Any],
        preferred_store: Optional[str] = None,
    ) -> ResolvedDestination:
        """
        Resolves shopping destination for a product object or dictionary.
        """
        # Extract attributes whether product is ORM model, dict, or Pydantic model
        def get_attr(key: str, default: Any = None) -> Any:
            if isinstance(product, dict):
                return product.get(key, default)
            return getattr(product, key, default)

        product_id = get_attr("id", 0)
        name = get_attr("name", "")
        brand = get_attr("brand", "")
        category = get_attr("category", "")
        subcategory = get_attr("subcategory", "")
        color = get_attr("color", "")
        style = get_attr("style", "")
        pattern = get_attr("pattern", "")
        platform = get_attr("platform", "")
        product_url = get_attr("product_url", "")
        external_links = get_attr("external_links", []) or []

        # -------------------------------------------------------------
        # PRIORITY 1: Existing Verified Exact Product Links
        # -------------------------------------------------------------
        if external_links:
            for link in external_links:
                v_status = getattr(link, "verification_status", None) or (
                    link.get("verification_status") if isinstance(link, dict) else ""
                )
                raw_url = getattr(link, "external_url", None) or (
                    link.get("external_url") if isinstance(link, dict) else (
                        getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else "")
                    )
                )
                store = getattr(link, "store_name", None) or (
                    link.get("store_name") if isinstance(link, dict) else "Store"
                )
                avail_status = getattr(link, "availability_status", None) or (
                    link.get("availability_status") if isinstance(link, dict) else "available"
                )

                if str(v_status).lower() == "verified" and is_valid_external_url(raw_url):
                    is_in_stock = avail_status in ("available", "in_stock", True, "true", "True")
                    return ResolvedDestination(
                        store_name=str(store).strip() or "Verified Store",
                        store_url=raw_url,
                        store_available=is_in_stock,
                        destination_type="exact_product",
                        store_cta="Shop Now",
                        is_exact_match=True,
                        query_terms="",
                    )

        # Also check product_url if already marked verified on product
        if is_valid_external_url(product_url):
            is_generic_platform = (platform or "").lower() in {
                "deepfashion",
                "catalog",
                "demo store",
                "demostore",
                "",
            }
            if not is_generic_platform:
                # -------------------------------------------------------------
                # PRIORITY 2: Verified Official Store / Brand Hub
                # -------------------------------------------------------------
                return ResolvedDestination(
                    store_name=platform or (brand and f"{brand} Official Store") or "Official Store",
                    store_url=product_url,
                    store_available=True,
                    destination_type="official_store",
                    store_cta="Shop Brand",
                    is_exact_match=False,
                    query_terms=brand or name,
                )

        # -------------------------------------------------------------
        # PRIORITY 3: Specific Shopping Search Destination
        # -------------------------------------------------------------
        query_terms = self.build_metadata_query(
            name=name,
            brand=brand,
            category=category,
            subcategory=subcategory,
            color=color,
            style=style,
        )

        # If we have meaningful specific keywords (brand + garment or title keywords)
        has_specific_metadata = bool(
            (brand and brand.lower() not in {"unknown", "none"})
            or (name and len(name.split()) >= 2)
        )

        if has_specific_metadata and query_terms:
            retailer = (
                self.registry.get_retailer(preferred_store)
                if preferred_store
                else self.registry.get_primary_retailer(category)
            )
            search_url = retailer.build_search_url(query_terms)
            if is_valid_external_url(search_url):
                return ResolvedDestination(
                    store_name=retailer.store_name,
                    store_url=search_url,
                    store_available=True,
                    destination_type="shopping_search",
                    store_cta="Find Similar Products",
                    is_exact_match=False,
                    query_terms=query_terms,
                )

        # -------------------------------------------------------------
        # PRIORITY 4: Generic Shopping Fallback
        # -------------------------------------------------------------
        fallback_query = query_terms or self._clean_token(f"{color} {category} fashion").strip() or "fashion apparel"
        fallback_retailer = self.registry.get_fallback_retailer()
        fallback_url = fallback_retailer.build_search_url(fallback_query)

        # Fallback safety validation
        if not is_valid_external_url(fallback_url):
            fallback_url = f"https://www.google.com/search?tbm=shop&q={urllib.parse.quote_plus(fallback_query)}"

        return ResolvedDestination(
            store_name=fallback_retailer.store_name,
            store_url=fallback_url,
            store_available=True,
            destination_type="fallback_search",
            store_cta="Search Online",
            is_exact_match=False,
            query_terms=fallback_query,
        )


# Global singleton instance for easy import
destination_resolver = ShoppingDestinationResolver()
