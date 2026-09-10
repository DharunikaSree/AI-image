"""
Verification test suite for View Product & Product Details URL Handling
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.product import sanitize_product_url, ProductResponse
from app.core.database import SessionLocal
from app.models.product import Product

def run_tests():
    print("=" * 70)
    print("   Running View Product & URL Sanitization Test Suite")
    print("=" * 70)

    # [Test 1] Backend URL Sanitizer unit tests
    print("\n[1] Testing URL Sanitizer logic...")
    assert sanitize_product_url("https://demo-store.example.com/product/30239") == "", "Should reject demo-store.example.com"
    assert sanitize_product_url("http://example.com/item/1") == "", "Should reject example.com"
    assert sanitize_product_url("http://localhost:3000/product/1") == "", "Should reject localhost"
    assert sanitize_product_url("http://127.0.0.1:8000/product/1") == "", "Should reject 127.0.0.1"
    assert sanitize_product_url("javascript:alert(1)") == "", "Should reject javascript: URI"
    assert sanitize_product_url("data:text/html,test") == "", "Should reject data: URI"
    assert sanitize_product_url("") == "", "Should handle empty string"
    assert sanitize_product_url(None) == "", "Should handle None"
    
    # Valid genuine external store URL
    valid_url = "https://www.nordstrom.com/s/floral-dress/12345"
    assert sanitize_product_url(valid_url) == valid_url, "Should accept valid external HTTPS URL"
    print("    -> Backend URL Sanitizer correctly validated and filtered all test cases (PASSED)")

    # [Test 2] Product API Endpoint Check for Product 30239
    print("\n[2] Testing GET /api/products/30239...")
    with TestClient(app) as client:
        res = client.get("/api/products/30239")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        print(f"    -> Product ID:    {data['id']}")
        print(f"    -> Product Name:  {data['name']}")
        print(f"    -> Category:      {data['category']}")
        print(f"    -> Price:         INR {data['price']}")
        print(f"    -> Product URL:   '{data['product_url']}' (Cleaned, no placeholder)")
        print(f"    -> Platform:      {data['platform']}")
        print(f"    -> External Links:{data.get('external_links', [])}")
        assert data["product_url"] == "", f"Expected empty product_url for DeepFashion item, got: {data['product_url']}"
        assert "external_links" in data, "ProductResponse must include external_links"
        assert isinstance(data["external_links"], list), "external_links must be a list"
        assert data["image_url"].startswith("/uploads/deepfashion/"), "Must use high-resolution DeepFashion image"

    # [Test 3] Check database state for placeholder URLs

    print("\n[3] Checking database for remaining placeholder URLs...")
    db = SessionLocal()
    count_placeholder = db.query(Product).filter(
        (Product.product_url.like("%demo-store%")) | 
        (Product.product_url.like("%example.com%")) |
        (Product.product_url.like("%localhost%"))
    ).count()
    db.close()
    assert count_placeholder == 0, f"Found {count_placeholder} remaining placeholder URLs in DB!"
    print(f"    -> Zero placeholder URLs exist in SQLite database (PASSED)")

    print("\n" + "=" * 70)
    print("   ALL VIEW PRODUCT & URL HANDLING TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
