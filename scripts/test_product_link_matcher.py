"""
Standalone Verification Suite for Product Link Matching Engine (Phase 8 Step 5)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.product_link_matcher import ProductLinkMatcher, MatchResult, is_valid_external_url


def run_tests():
    print("=" * 75)
    print("   PHASE 8 STEP 5: PRODUCT LINK MATCHER TEST SUITE")
    print("=" * 75)

    matcher = ProductLinkMatcher(threshold=0.75)

    # 1. Test URL Sanitizer
    print("\n[1] Testing URL Sanitizer...")
    assert is_valid_external_url("https://www.myntra.com/shirts/turtle/15970") is True
    assert is_valid_external_url("http://www.myntra.com/shirts/turtle/15970") is False
    assert is_valid_external_url("https://demo-store.example.com/item/1") is False
    assert is_valid_external_url("https://localhost:8000/product/1") is False
    assert is_valid_external_url("https://example.com/product") is False
    print("    -> URL Sanitizer correctly accepted valid HTTPS and rejected HTTP/placeholders (PASSED)")

    # 2. Test High-Confidence Valid Match
    print("\n[2] Testing High-Confidence Matching...")
    catalog_product = {
        "id": 15970,
        "name": "Turtle Check Men Navy Blue Shirt",
        "brand": "Turtle",
        "category": "Shirt",
        "subcategory": "Shirts",
        "color": "Navy",
        "style": "Casual",
    }
    candidate_valid = {
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
    match = matcher.match(catalog_product, [candidate_valid])
    assert match is not None, "Expected valid match"
    assert match.product_id == 15970
    assert match.store_name == "Myntra"
    assert match.match_score >= 0.85
    assert match.verification_status == "verified"
    print(f"    -> Matched with score: {match.match_score:.3f} | Reasons: {match.reasons} (PASSED)")

    # 3. Test Brand Collision Guardrail
    print("\n[3] Testing Brand Mismatch Rejection...")
    candidate_wrong_brand = {
        "store_name": "Amazon",
        "external_url": "https://www.amazon.in/dp/B001",
        "product_name": "Puma Check Men Navy Blue Shirt",
        "brand": "Puma",  # Different brand
        "category": "Shirt",
        "color": "Navy",
        "style": "Casual",
        "verification_status": "verified",
    }
    match_wrong_brand = matcher.match(catalog_product, [candidate_wrong_brand])
    assert match_wrong_brand is None, "Must reject brand mismatch"
    print("    -> Cross-brand collision successfully blocked (PASSED)")

    # 4. Test Category Collision Guardrail
    print("\n[4] Testing Category Mismatch Rejection...")
    candidate_wrong_cat = {
        "store_name": "Myntra",
        "external_url": "https://www.myntra.com/shoes/turtle/15970",
        "product_name": "Turtle Navy Blue Shoes",
        "brand": "Turtle",
        "category": "Shoes",  # Different category
        "color": "Navy",
        "style": "Casual",
        "verification_status": "verified",
    }
    match_wrong_cat = matcher.match(catalog_product, [candidate_wrong_cat])
    assert match_wrong_cat is None, "Must reject category mismatch"
    print("    -> Category collision successfully blocked (PASSED)")

    # 5. Test Status Integrity
    print("\n[5] Testing Verification Status Integrity...")
    candidate_unverified = {
        "store_name": "Ajio",
        "external_url": "https://www.ajio.com/turtle-shirt/p/15970",
        "product_name": "Turtle Men Navy Blue Shirt",
        "brand": "Turtle",
        "category": "Shirt",
        "color": "Navy",
        "style": "Casual",
        "verification_status": "unverified",
    }
    match_unverified = matcher.match(catalog_product, [candidate_unverified])
    assert match_unverified is not None
    assert match_unverified.verification_status == "unverified", "Never promote unverified to verified"
    print("    -> Preserved unverified status accurately without promotion (PASSED)")

    # 6. Test Dictionary Output Structure
    print("\n[6] Testing Output Dictionary Contract...")
    dict_out = match.to_dict()
    assert "product_id" in dict_out
    assert "store_name" in dict_out
    assert "external_url" in dict_out
    assert "match_score" in dict_out
    assert "verification_status" in dict_out
    print(f"    -> Output Dict: {dict_out} (PASSED)")

    print("\n" + "=" * 75)
    print("   ALL PRODUCT LINK MATCHER TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
