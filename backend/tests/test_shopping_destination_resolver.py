"""
Unit and Integration Tests for Universal Shopping Destination Resolver (Phase 8 Step 13)

Covers all 15 required test scenarios:
1. Exact verified URL has highest priority
2. Official store fallback
3. Shopping search fallback
4. Generic fallback
5. Brand/name/category metadata encoding
6. Special characters in product names
7. Empty brand handling
8. Empty product name handling
9. HTTP insecure URL rejection
10. Placeholder domain rejection (example.com, demo-store)
11. Private IP and loopback SSRF rejection
12. No fake product ID generation
13. Exact URL is never replaced by generated search
14. destination_type correctness across all tiers
15. CTA text correctness across all tiers
"""
import urllib.parse
import pytest

from app.models.product import Product, ProductExternalLink
from app.services.shopping_destination_resolver import (
    ShoppingDestinationResolver,
    RetailerRegistry,
    RetailerConfig,
    destination_resolver,
)


@pytest.fixture
def resolver():
    return ShoppingDestinationResolver()


# -------------------------------------------------------------
# 1. Exact Verified URL has Highest Priority
# -------------------------------------------------------------
def test_exact_verified_url_highest_priority(resolver):
    product = {
        "id": 15970,
        "name": "Turtle Check Men Navy Blue Shirt",
        "brand": "Turtle",
        "category": "Shirt",
        "subcategory": "Shirts",
        "color": "Navy",
        "style": "Casual",
        "external_links": [
            {
                "store_name": "Myntra",
                "external_url": "https://www.myntra.com/shirts/turtle/15970/buy",
                "verification_status": "verified",
                "availability_status": "available",
            }
        ],
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "exact_product"
    assert dest.store_cta == "Shop Now"
    assert dest.store_name == "Myntra"
    assert dest.store_url == "https://www.myntra.com/shirts/turtle/15970/buy"
    assert dest.store_available is True
    assert dest.is_exact_match is True


# -------------------------------------------------------------
# 2. Official Store Fallback
# -------------------------------------------------------------
def test_official_store_fallback(resolver):
    product = {
        "id": 53759,
        "name": "Puma Men Grey T-shirt",
        "brand": "Puma",
        "category": "T-Shirt",
        "platform": "Puma Official Store",
        "product_url": "https://in.puma.com/in/en/store/mens-apparel",
        "external_links": [],
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "official_store"
    assert dest.store_cta == "Shop Brand"
    assert "puma" in dest.store_url.lower()
    assert dest.is_exact_match is False


# -------------------------------------------------------------
# 3. Shopping Search Fallback (Brand + Attributes)
# -------------------------------------------------------------
def test_shopping_search_fallback(resolver):
    product = {
        "id": 39386,
        "name": "Peter England Men Party Blue Jeans",
        "brand": "Peter England",
        "category": "Jeans",
        "subcategory": "Jeans",
        "color": "Blue",
        "style": "Party",
        "external_links": [],
        "product_url": "",
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "shopping_search"
    assert dest.store_cta == "Find Similar Products"
    assert dest.is_exact_match is False
    assert dest.store_available is True
    assert "https://" in dest.store_url
    assert "Peter+England" in dest.store_url or "peter" in dest.store_url.lower()


# -------------------------------------------------------------
# 4. Generic Fallback (Minimal/No Brand)
# -------------------------------------------------------------
def test_generic_fallback_minimal_metadata(resolver):
    product = {
        "id": 9999,
        "name": "Sample",
        "brand": "",
        "category": "Shoes",
        "color": "Red",
        "external_links": [],
        "product_url": "",
    }
    dest = resolver.resolve(product)
    assert dest.destination_type in ("shopping_search", "fallback_search")
    assert dest.store_cta in ("Find Similar Products", "Search Online")
    assert dest.is_exact_match is False
    assert "https://" in dest.store_url


# -------------------------------------------------------------
# 5. Brand, Name, and Category Metadata Encoding
# -------------------------------------------------------------
def test_metadata_query_encoding(resolver):
    query = resolver.build_metadata_query(
        name="Arrow Men Formal White Slim Fit Shirt",
        brand="Arrow",
        category="Shirt",
        subcategory="Shirts",
        color="White",
        style="Formal",
    )
    assert "Arrow" in query
    assert "Shirt" in query
    assert "White" in query

    encoded = urllib.parse.quote_plus(query)
    assert " " not in encoded
    assert "%20" not in encoded or "+" in encoded


# -------------------------------------------------------------
# 6. Special Characters in Product Names
# -------------------------------------------------------------
def test_special_characters_handling(resolver):
    product = {
        "id": 1234,
        "name": "Levi's Men 511™ Slim Fit Jeans & Co. (Dark Blue)",
        "brand": "Levi's",
        "category": "Jeans",
        "color": "Dark Blue",
        "external_links": [],
        "product_url": "",
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "shopping_search"
    assert dest.store_cta == "Find Similar Products"
    # Ensure URL is properly formed and valid without broken chars
    assert "Levi" in dest.store_url
    assert " " not in dest.store_url
    assert dest.store_url.startswith("https://")


# -------------------------------------------------------------
# 7. Empty Brand Handling
# -------------------------------------------------------------
def test_empty_brand_handling(resolver):
    product = {
        "id": 5555,
        "name": "Women Floral Print Summer Dress",
        "brand": None,
        "category": "Dress",
        "color": "Floral",
        "external_links": [],
    }
    dest = resolver.resolve(product)
    assert dest.destination_type in ("shopping_search", "fallback_search")
    assert dest.store_url.startswith("https://")
    assert "Dress" in dest.query_terms or "Floral" in dest.query_terms


# -------------------------------------------------------------
# 8. Empty Product Name Handling
# -------------------------------------------------------------
def test_empty_product_name_handling(resolver):
    product = {
        "id": 6666,
        "name": "",
        "brand": "Casio",
        "category": "Watches",
        "color": "Silver",
        "external_links": [],
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "shopping_search"
    assert "Casio" in dest.query_terms
    assert dest.store_url.startswith("https://")


# -------------------------------------------------------------
# 9. HTTP Insecure URL Rejection
# -------------------------------------------------------------
def test_http_url_rejection(resolver):
    product = {
        "id": 7777,
        "name": "Test Shirt",
        "brand": "TestBrand",
        "category": "Shirt",
        "external_links": [
            {
                "store_name": "InsecureStore",
                "external_url": "http://www.myntra.com/insecure-shirt/1",
                "verification_status": "verified",
            }
        ],
    }
    dest = resolver.resolve(product)
    # The insecure link must be rejected and fallback to shopping search
    assert dest.destination_type != "exact_product"
    assert dest.store_url.startswith("https://")
    assert not dest.store_url.startswith("http://")


# -------------------------------------------------------------
# 10. Placeholder Domain Rejection
# -------------------------------------------------------------
def test_placeholder_domain_rejection(resolver):
    product = {
        "id": 8888,
        "name": "Placeholder Shirt",
        "brand": "DummyBrand",
        "category": "Shirt",
        "product_url": "https://demo-store.example.com/product/8888",
        "external_links": [
            {
                "store_name": "FakeStore",
                "external_url": "https://example.com/fake-product",
                "verification_status": "verified",
            }
        ],
    }
    dest = resolver.resolve(product)
    # Placeholder URLs must never be emitted as exact_product
    assert "example.com" not in dest.store_url
    assert "demo-store" not in dest.store_url
    assert dest.destination_type != "exact_product"
    assert dest.store_url.startswith("https://")


# -------------------------------------------------------------
# 11. Private IP & Loopback SSRF Rejection
# -------------------------------------------------------------
def test_private_ip_ssrf_rejection(resolver):
    product = {
        "id": 9999,
        "name": "SSRF Attempt Item",
        "brand": "Attacker",
        "category": "Shirt",
        "external_links": [
            {
                "store_name": "Localhost",
                "external_url": "https://127.0.0.1:8000/admin/delete",
                "verification_status": "verified",
            },
            {
                "store_name": "PrivateSubnet",
                "external_url": "https://192.168.1.1/router",
                "verification_status": "verified",
            },
        ],
    }
    dest = resolver.resolve(product)
    assert "127.0.0.1" not in dest.store_url
    assert "192.168.1.1" not in dest.store_url
    assert dest.destination_type != "exact_product"


# -------------------------------------------------------------
# 12. No Fake Product ID Generation
# -------------------------------------------------------------
def test_no_fake_product_id_generation(resolver):
    product = {
        "id": 44442,
        "name": "Pure DeepFashion Catalog Item",
        "brand": "CatalogBrand",
        "category": "Shirt",
        "external_links": [],
        "product_url": "",
    }
    dest = resolver.resolve(product)
    # Destination must be a legitimate search query, not a guessed item page like /product/44442
    assert dest.destination_type == "shopping_search"
    assert "/search" in dest.store_url or "/s?" in dest.store_url
    assert "/44442" not in dest.store_url
    assert dest.is_exact_match is False


# -------------------------------------------------------------
# 13. Exact URL is Never Replaced
# -------------------------------------------------------------
def test_exact_url_never_replaced_by_search(resolver):
    verified_url = "https://www.tatacliq.com/titan-women-silver-watch/p-mp0000000059263"
    product = {
        "id": 59263,
        "name": "Titan Women Silver Watch",
        "brand": "Titan",
        "category": "Watches",
        "external_links": [
            {
                "store_name": "Tata CLiQ",
                "external_url": verified_url,
                "verification_status": "verified",
                "availability_status": "available",
            }
        ],
    }
    dest = resolver.resolve(product)
    assert dest.destination_type == "exact_product"
    assert dest.store_url == verified_url
    assert dest.store_cta == "Shop Now"


# -------------------------------------------------------------
# 14. Destination Type Correctness Across All Tiers
# -------------------------------------------------------------
def test_destination_type_hierarchy_correctness(resolver):
    # Tier 1
    t1 = resolver.resolve({
        "id": 1,
        "name": "Item",
        "brand": "B",
        "category": "C",
        "external_links": [{"external_url": "https://www.myntra.com/item/1", "verification_status": "verified"}],
    })
    assert t1.destination_type == "exact_product"

    # Tier 2
    t2 = resolver.resolve({
        "id": 2,
        "name": "Brand Item",
        "brand": "Nike",
        "category": "Shoes",
        "platform": "Nike Official Store",
        "product_url": "https://www.nike.com/in/store",
    })
    assert t2.destination_type == "official_store"

    # Tier 3
    t3 = resolver.resolve({
        "id": 3,
        "name": "Puma Black Running Shoes",
        "brand": "Puma",
        "category": "Shoes",
        "color": "Black",
    })
    assert t3.destination_type == "shopping_search"

    # Tier 4
    t4 = resolver.resolve({
        "id": 4,
        "name": "",
        "brand": "",
        "category": "",
    })
    assert t4.destination_type == "fallback_search"


# -------------------------------------------------------------
# 15. CTA Text Correctness Across All Tiers
# -------------------------------------------------------------
def test_cta_text_correctness_across_tiers(resolver):
    cta_map = {
        "exact_product": "Shop Now",
        "official_store": "Shop Brand",
        "shopping_search": "Find Similar Products",
        "fallback_search": "Search Online",
    }

    p_t1 = {"id": 1, "external_links": [{"external_url": "https://www.myntra.com/1", "verification_status": "verified"}]}
    assert resolver.resolve(p_t1).store_cta == cta_map["exact_product"]

    p_t2 = {"id": 2, "platform": "Brand Store", "product_url": "https://www.brandstore.com/in"}
    assert resolver.resolve(p_t2).store_cta == cta_map["official_store"]

    p_t3 = {"id": 3, "brand": "Adidas", "category": "Shoes", "name": "Adidas Running Shoes"}
    assert resolver.resolve(p_t3).store_cta == cta_map["shopping_search"]

    p_t4 = {"id": 4, "brand": "", "name": "", "category": ""}
    assert resolver.resolve(p_t4).store_cta == cta_map["fallback_search"]
