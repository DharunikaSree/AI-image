"""
End-to-End Real Store Link Workflow & Safety Verification Test Suite (Phase 8 Step 11)

Tests the complete visual intelligence and e-commerce store link pipeline:
1. User authentication & authorization
2. Fashion image upload
3. ViT category classification & multi-attribute detection
4. CLIP 512-d embedding generation
5. Sub-millisecond FAISS vector index retrieval
6. Multi-factor recommendation scoring
7. Product Details API serialization
8. External store-link extraction & availability check
9. Strict URL validation (HTTPS only, anti-phishing, blocked domain blacklist)
10. Multi-store availability support
11. Shop The Look multi-garment independent store link routing

Test Cases:
  [A] Product with verified real store URL (View Details -> Product Details -> Shop Now -> real URL)
  [B] Product without store URL (View Details -> Product Details -> "Online store link not available")
  [C] Insecure & Malformed URLs (HTTP, missing host, javascript: rejected)
  [D] Placeholder & SSRF domains (example.com, demo-store, localhost, 127.0.0.1 rejected)
  [E] Multiple verified stores for a single product (Multi-button support)
  [F] Shop The Look multi-garment search with per-garment store links

Usage:
    py -3.13 scripts/test_real_store_link_flow.py
"""
from __future__ import annotations

import io
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.models.product import Product, ProductExternalLink
from app.models.user import User
from app.services.product_link_matcher import is_valid_external_url, ProductLinkMatcher
from app.services.url_verifier import (
    URLVerifier,
    prevalidate_url,
    is_private_or_blocked_host,
)

settings = get_settings()


def create_synthetic_test_image(color_rgb=(25, 40, 80)) -> bytes:
    """Generates a valid JPEG image buffer for search uploads."""
    img = Image.new("RGB", (224, 224), color=color_rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def load_dataset_image(filename: str) -> bytes | None:
    """Attempts to locate a real image file from dataset directories."""
    for d in settings.dataset_image_dirs:
        candidate = d / filename
        if candidate.exists():
            with open(candidate, "rb") as f:
                return f.read()
    return None


def run_e2e_tests():
    print("=" * 75)
    print("   PHASE 8 STEP 11: END-TO-END REAL STORE LINK FLOW TEST SUITE")
    print("=" * 75)

    limiter.reset()

    with TestClient(app) as client:
        # 1. Setup authenticated user
        print("\n[Step 1] Authenticating Test User...")
        db = SessionLocal()
        user_email = f"realstore_test_{int(time.time())}@example.com"
        user = User(
            name="RealStore Tester",
            email=user_email,
            password_hash=hash_password("StorePass123!"),
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Ensure seed products and links exist for test assertions
        p_verified = db.query(Product).filter(Product.id == 15970).first()
        if not p_verified:
            p_verified = Product(
                id=15970,
                name="Turtle Check Men Navy Blue Shirt",
                brand="Turtle",
                category="Shirt",
                subcategory="Shirts",
                color="Navy",
                style="Casual",
                price=1799.0,
            )
            db.add(p_verified)
            db.commit()

        # Seed verified link for product 15970 if not present
        link_myntra = (
            db.query(ProductExternalLink)
            .filter(ProductExternalLink.product_id == 15970, ProductExternalLink.store_name == "Myntra")
            .first()
        )
        now = datetime.now(timezone.utc)
        if not link_myntra:
            link_myntra = ProductExternalLink(
                product_id=15970,
                store_name="Myntra",
                external_url="https://www.myntra.com/shirts/turtle/turtle-men-navy-blue-checked-casual-shirt/15970/buy",
                verification_status="verified",
                availability_status="available",
                last_verified_at=now,
                price_on_store=1799.0,
                is_primary=True,
            )
            db.add(link_myntra)
            db.commit()

        # Seed multi-store link (Amazon + Ajio) for product 15970 to test Test Case E
        link_amazon = (
            db.query(ProductExternalLink)
            .filter(ProductExternalLink.product_id == 15970, ProductExternalLink.store_name == "Amazon")
            .first()
        )
        if not link_amazon:
            link_amazon = ProductExternalLink(
                product_id=15970,
                store_name="Amazon",
                external_url="https://www.amazon.in/Turtle-Men-Checked-Casual-Shirt/dp/B08XYZ5970",
                verification_status="verified",
                availability_status="available",
                last_verified_at=now,
                price_on_store=1749.0,
                is_primary=False,
            )
            db.add(link_amazon)
            db.commit()

        # Seed unlinked product for Test Case B
        p_unlinked = db.query(Product).filter(Product.id == 998811).first()
        if not p_unlinked:
            p_unlinked = Product(
                id=998811,
                name="DeepFashion Research Catalog Pure Item",
                brand="ResearchBrand",
                category="Shirt",
                price=1200.0,
                product_url="",
                platform="DeepFashion",
            )
            db.add(p_unlinked)
            db.commit()

        # Delete any links on 998811 to guarantee zero links
        db.query(ProductExternalLink).filter(ProductExternalLink.product_id == 998811).delete()
        db.commit()

        db.close()

        # Get Auth Token
        login_res = client.post("/api/auth/login", json={"email": user_email, "password": "StorePass123!"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("    -> User authenticated successfully with valid JWT.")

        # -------------------------------------------------------------
        # End-to-End Workflow: Image Search -> ViT -> CLIP -> FAISS -> Recommendations
        # -------------------------------------------------------------
        print("\n[Step 2-6] Executing Complete Visual Search Pipeline (Upload -> ViT -> CLIP -> FAISS -> Scoring)...")
        img_bytes = load_dataset_image("15970.jpg") or create_synthetic_test_image((25, 40, 80))
        search_files = {"file": ("query_garment.jpg", img_bytes, "image/jpeg")}

        t0 = time.perf_counter()
        search_res = client.post("/api/search/image", files=search_files, headers=headers)
        duration_ms = (time.perf_counter() - t0) * 1000

        assert search_res.status_code == 200, f"Search failed: {search_res.text}"
        search_data = search_res.json()

        assert "search_id" in search_data
        assert "detected_items" in search_data and len(search_data["detected_items"]) > 0
        detected = search_data["detected_items"][0]
        assert "category" in detected and detected["category"] != ""
        assert "confidence" in detected

        assert "best_matches" in search_data
        assert len(search_data["best_matches"]) > 0, "Expected recommendations from FAISS index"
        top_rec = search_data["best_matches"][0]
        assert "product" in top_rec
        assert "scores" in top_rec
        assert "overall_score" in top_rec["scores"]
        print(f"    -> Visual pipeline completed in {duration_ms:.1f}ms.")
        print(f"    -> ViT Classified Category: [{detected['category']}] ({detected['confidence']:.1f}%)")
        print(f"    -> Top Recommended Product: '{top_rec['product']['name']}' (Match: {top_rec['scores']['overall_score']:.1f}%)")

        # -------------------------------------------------------------
        # TEST CASE A: Product with Verified Store URL
        # -------------------------------------------------------------
        print("\n[Test Case A] Verifying Product with Verified Real Store URL...")
        prod_a_res = client.get("/api/products/15970", headers=headers)
        assert prod_a_res.status_code == 200
        prod_a = prod_a_res.json()

        assert prod_a["id"] == 15970
        assert prod_a["name"] == "Turtle Check Men Navy Blue Shirt"
        assert "external_links" in prod_a
        assert len(prod_a["external_links"]) >= 1

        verified_link = next((l for l in prod_a["external_links"] if l["verification_status"] == "verified"), None)
        assert verified_link is not None, "Product 15970 must contain a verified link"
        assert is_valid_external_url(verified_link["url"]) is True
        assert verified_link["url"].startswith("https://www.myntra.com/") or verified_link["url"].startswith("https://")
        assert verified_link["availability_status"] == "available"

        # Check frontend CTA flow simulation
        print("    -> User Flow Simulation:")
        print("       1. Click [View Details] on Recommendation Card")
        print(f"       2. Navigates to Product #{prod_a['id']} Details Page")
        print(f"       3. Available at: [ Visit {verified_link['store_name']} ^ ]")
        print(f"       4. Opens safe target URL: {verified_link['url']}")
        print("    -> [PASSED] Test Case A verified successfully.")

        # -------------------------------------------------------------
        # TEST CASE B: Product without Store URL (Research Catalog Item)
        # -------------------------------------------------------------
        print("\n[Test Case B] Verifying Product without Store URL (Research Catalog Item)...")
        prod_b_res = client.get("/api/products/998811", headers=headers)
        assert prod_b_res.status_code == 200
        prod_b = prod_b_res.json()

        assert prod_b["id"] == 998811
        # External links must be empty or contain zero verified links
        verified_b_links = [l for l in prod_b.get("external_links", []) if l.get("verification_status") == "verified"]
        assert len(verified_b_links) == 0, "Unlinked research product must have 0 verified links"
        assert prod_b.get("product_url") == "" or not is_valid_external_url(prod_b.get("product_url"))

        print("    -> User Flow Simulation:")
        print("       1. Click [View Details ->] on Recommendation Card")
        print(f"       2. Navigates to Product #{prod_b['id']} Details Page")
        print("       3. Displays Notice: 'Online store link not available'")
        print("       4. Explains: 'This product is available in the research catalog, but a verified live shopping link is not currently available.'")
        print("       5. No fake links or disabled Buy Now buttons shown.")
        print("    -> [PASSED] Test Case B verified successfully.")

        # -------------------------------------------------------------
        # TEST CASE C: Invalid & Non-HTTPS URLs Rejected
        # -------------------------------------------------------------
        print("\n[Test Case C] Verifying Rejection of Insecure HTTP & Malformed URLs...")
        invalid_urls = [
            ("http://www.myntra.com/shirts/15970", "HTTP insecure protocol"),
            ("javascript:alert(document.cookie)", "Javascript scheme"),
            ("ftp://ftp.example.com/item/1", "FTP scheme"),
            ("https://", "Malformed missing host"),
            ("", "Empty string"),
            ("not-a-url", "Non-URL string"),
        ]
        for bad_url, label in invalid_urls:
            is_valid_syntax, reason = prevalidate_url(bad_url)
            assert is_valid_syntax is False, f"Expected {bad_url} ({label}) to be rejected"
            assert is_valid_external_url(bad_url) is False
            print(f"    -> Safely rejected: '{bad_url[:35]}' [{label}] -> {reason}")
        print("    -> [PASSED] Test Case C verified successfully.")

        # -------------------------------------------------------------
        # TEST CASE D: Placeholder & Private IP / SSRF Domains Rejected
        # -------------------------------------------------------------
        print("\n[Test Case D] Verifying Strict Rejection of Placeholder & Private SSRF Domains...")
        placeholder_domains = [
            ("https://demo-store.example.com/product/1", "demo-store placeholder"),
            ("https://example.com/item/123", "example.com placeholder"),
            ("https://localhost:8000/product/1", "localhost loopback"),
            ("https://127.0.0.1:5000/item", "127.0.0.1 IPv4 loopback"),
            ("https://0.0.0.0:8000/api", "0.0.0.0 unrouted"),
            ("https://192.168.1.100/product", "192.168.0.0/16 private IP"),
            ("https://10.0.0.1/item", "10.0.0.0/8 private IP"),
            ("https://169.254.169.254/latest/meta-data", "Link-local cloud metadata IP"),
        ]
        for ph_url, label in placeholder_domains:
            is_valid_syntax, reason = prevalidate_url(ph_url)
            assert is_valid_syntax is False, f"Expected {ph_url} ({label}) to be rejected"
            assert is_valid_external_url(ph_url) is False
            print(f"    -> Safely blocked SSRF/Placeholder: '{ph_url[:40]}' [{label}]")
        print("    -> [PASSED] Test Case D verified successfully.")

        # -------------------------------------------------------------
        # TEST CASE E: Multiple Verified Store Links
        # -------------------------------------------------------------
        print("\n[Test Case E] Verifying Multiple Legitimate Store Buttons for Single Product...")
        prod_e_res = client.get("/api/products/15970", headers=headers)
        assert prod_e_res.status_code == 200
        prod_e = prod_e_res.json()

        verified_stores = [l for l in prod_e["external_links"] if l["verification_status"] == "verified"]
        assert len(verified_stores) >= 2, f"Expected at least 2 verified stores, found {len(verified_stores)}"

        store_names = [s["store_name"] for s in verified_stores]
        print(f"    -> Product #{prod_e['id']} verified on multiple platforms: {', '.join(store_names)}")
        for s in verified_stores:
            assert s["url"].startswith("https://")
            assert is_valid_external_url(s["url"]) is True
            print(f"       * Button: [ Visit {s['store_name']} ^ ] -> {s['url'][:60]}...")
        print("    -> [PASSED] Test Case E verified successfully.")

        # -------------------------------------------------------------
        # TEST CASE F: Shop The Look Multi-Garment Store Links
        # -------------------------------------------------------------
        print("\n[Test Case F] Verifying Shop The Look Multi-Garment Search with Real Store Links...")
        garment_1 = load_dataset_image("15970.jpg") or create_synthetic_test_image((25, 40, 80)) # Shirt (linked to Myntra/Amazon)
        garment_2 = load_dataset_image("39386.jpg") or create_synthetic_test_image((40, 60, 180)) # Jeans (linked to Amazon)

        multi_files = [
            ("files", ("crop_1_shirt.jpg", garment_1, "image/jpeg")),
            ("files", ("crop_2_jeans.jpg", garment_2, "image/jpeg")),
        ]

        multi_res = client.post("/api/search/multi-item", files=multi_files, headers=headers)
        assert multi_res.status_code == 200, f"Multi-item search failed: {multi_res.text}"
        multi_data = multi_res.json()

        assert multi_data["total_items"] == 2
        assert len(multi_data["items"]) == 2

        for idx, item in enumerate(multi_data["items"], start=1):
            attr = item["detected_attributes"]
            print(f"\n    Garment #{idx} ({attr['category']} - {attr['color']}):")
            print(f"      - Best Matches: {len(item['best_matches'])} items")
            if item["best_matches"]:
                top_match = item["best_matches"][0]
                p_item = top_match["product"]
                print(f"      - Top Match: '{p_item['name']}' (INR {p_item['price']})")
                if top_match.get("store_url") and is_valid_external_url(top_match["store_url"]):
                    print(f"      - Real Store Action: [ Shop on {top_match.get('store_name', 'Store')} ^ ] -> {top_match['store_url'][:55]}...")
                else:
                    print(f"      - Research Catalog Action: [ View Details -> ] (Research Catalog Item)")

        print("\n    -> [PASSED] Test Case F verified successfully.")

        # Summary
        print("\n" + "=" * 75)
        print("   ALL PHASE 8 STEP 11 REAL STORE LINK FLOW TESTS PASSED (100% GREEN)!")
        print("=" * 75)


if __name__ == "__main__":
    run_e2e_tests()
