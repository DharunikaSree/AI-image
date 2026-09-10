"""
Unit tests for Product Link Matcher (Phase 8 Step 5)
"""
import pytest
from app.services.product_link_matcher import ProductLinkMatcher, MatchResult, is_valid_external_url


def test_url_sanitizer_validation():
    # Valid HTTPS URLs
    assert is_valid_external_url("https://www.myntra.com/shirts/turtle/15970") is True
    assert is_valid_external_url("https://www.amazon.in/dp/B08XYZ1234") is True
    assert is_valid_external_url("https://in.puma.com/pd/123.html") is True

    # Insecure or Placeholder URLs
    assert is_valid_external_url("http://www.myntra.com/shirts/turtle/15970") is False  # HTTP rejected
    assert is_valid_external_url("https://demo-store.example.com/product/1") is False  # Demo domain
    assert is_valid_external_url("https://example.com/item") is False  # example.com rejected
    assert is_valid_external_url("https://localhost:8000/product/1") is False  # localhost rejected
    assert is_valid_external_url("javascript:alert(1)") is False  # javascript URI
    assert is_valid_external_url("") is False
    assert is_valid_external_url(None) is False


def test_high_confidence_match():
    matcher = ProductLinkMatcher(threshold=0.75)

    catalog_product = {
        "id": 15970,
        "name": "Turtle Check Men Navy Blue Shirt",
        "brand": "Turtle",
        "category": "Shirt",
        "subcategory": "Shirts",
        "color": "Navy",
        "style": "Casual",
    }

    candidates = [
        {
            "store_name": "Myntra",
            "external_url": "https://www.myntra.com/shirts/turtle/turtle-men-navy-blue-checked-casual-shirt/15970/buy",
            "product_name": "Turtle Men Navy Blue Checked Casual Shirt",
            "brand": "Turtle",
            "category": "Shirt",
            "subcategory": "Shirts",
            "color": "Navy",
            "style": "Casual",
            "verification_status": "verified",
        }
    ]

    result = matcher.match(catalog_product, candidates)
    assert result is not None
    assert isinstance(result, MatchResult)
    assert result.product_id == 15970
    assert result.store_name == "Myntra"
    assert result.external_url == "https://www.myntra.com/shirts/turtle/turtle-men-navy-blue-checked-casual-shirt/15970/buy"
    assert result.match_score >= 0.85
    assert result.verification_status == "verified"

    # Test dictionary export
    dict_res = result.to_dict()
    assert dict_res["product_id"] == 15970
    assert dict_res["store_name"] == "Myntra"
    assert dict_res["match_score"] == round(result.match_score, 3)


def test_brand_mismatch_rejection():
    matcher = ProductLinkMatcher(threshold=0.70)

    catalog_product = {
        "id": 53759,
        "name": "Puma Men Grey T-shirt",
        "brand": "Puma",
        "category": "T-Shirt",
        "color": "Gray",
        "style": "Casual",
    }

    # Candidate with different brand (Adidas) even with similar name
    candidates = [
        {
            "store_name": "Myntra",
            "external_url": "https://www.myntra.com/tshirts/adidas/adidas-men-grey-tshirt/53759",
            "product_name": "Adidas Men Grey T-shirt",
            "brand": "Adidas",
            "category": "T-Shirt",
            "color": "Gray",
            "style": "Casual",
            "verification_status": "unverified",
        }
    ]

    result = matcher.match(catalog_product, candidates)
    # Must be completely rejected due to brand mismatch guardrail
    assert result is None


def test_category_mismatch_rejection():
    matcher = ProductLinkMatcher(threshold=0.60)

    catalog_product = {
        "id": 1163,
        "name": "Nike Men Running Shoes",
        "brand": "Nike",
        "category": "Shoes",
        "color": "Black",
        "style": "Sporty",
    }

    # Same brand and color, but completely different clothing category
    candidates = [
        {
            "store_name": "Nike Official",
            "external_url": "https://www.nike.com/in/t/nike-black-running-jacket/1163",
            "product_name": "Nike Men Running Jacket",
            "brand": "Nike",
            "category": "Jacket",
            "color": "Black",
            "style": "Sporty",
            "verification_status": "verified",
        }
    ]

    result = matcher.match(catalog_product, candidates)
    assert result is None


def test_never_promotes_unverified_status():
    matcher = ProductLinkMatcher(threshold=0.75)

    catalog_product = {
        "id": 39386,
        "name": "Peter England Men Party Blue Jeans",
        "brand": "Peter England",
        "category": "Jeans",
        "color": "Blue",
        "style": "Casual",
    }

    candidates = [
        {
            "store_name": "Amazon",
            "external_url": "https://www.amazon.in/Peter-England-Men-Jeans/dp/B08XYZ1234",
            "product_name": "Peter England Men Blue Slim Jeans",
            "brand": "Peter England",
            "category": "Jeans",
            "color": "Blue",
            "style": "Casual",
            "verification_status": "unverified",
        }
    ]

    result = matcher.match(catalog_product, candidates)
    assert result is not None
    # Must preserve original unverified status, never fabricate 'verified'
    assert result.verification_status == "unverified"


def test_rejects_placeholder_candidate_url():
    matcher = ProductLinkMatcher(threshold=0.50)

    catalog_product = {
        "id": 30805,
        "name": "Fabindia Men Striped Green Shirt",
        "brand": "FabIndia",
        "category": "Shirt",
        "color": "Green",
    }

    candidates = [
        {
            "store_name": "Demo Store",
            "external_url": "https://demo-store.example.com/item/30805",
            "product_name": "Fabindia Men Striped Green Shirt",
            "brand": "FabIndia",
            "category": "Shirt",
            "color": "Green",
            "verification_status": "verified",
        }
    ]

    result = matcher.match(catalog_product, candidates)
    assert result is None  # Placeholder URL strictly rejected


def test_visual_similarity_boost():
    matcher = ProductLinkMatcher(threshold=0.75)

    catalog_product = {
        "id": 100,
        "name": "Classic Black Leather Jacket",
        "brand": "Urban Basics",
        "category": "Jacket",
        "color": "Black",
        "style": "Casual",
    }

    candidate = {
        "store_name": "Official Store",
        "external_url": "https://www.urbanbasics.com/products/leather-jacket-black",
        "product_name": "Black Leather Casual Jacket",
        "brand": "Urban Basics",
        "category": "Jacket",
        "color": "Black",
        "style": "Casual",
        "verification_status": "verified",
    }

    score_low_vis, _ = matcher.compute_match_confidence(catalog_product, candidate, visual_similarity=0.3)
    score_high_vis, _ = matcher.compute_match_confidence(catalog_product, candidate, visual_similarity=0.95)

    assert score_high_vis > score_low_vis
    assert score_high_vis >= 0.85
