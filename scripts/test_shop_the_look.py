"""
Comprehensive test suite for Phase 7 Task 8:
Shop The Look / Multi-Item Fashion Search & Performance Benchmarks.
"""
import io
import json
import os
import sys
import time
from pathlib import Path
from PIL import Image

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
from app.models.user import User

settings = get_settings()

def create_synthetic_garment_image(color_rgb=(30, 40, 80)) -> bytes:
    img = Image.new("RGB", (224, 224), color=color_rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def load_dataset_image(filename: str) -> bytes | None:
    for d in settings.dataset_image_dirs:
        candidate = d / filename
        if candidate.exists():
            with open(candidate, "rb") as f:
                return f.read()
    return None

def run_tests():
    print("=" * 75)
    print("   Running Phase 7 Task 8 Shop The Look Multi-Item Search Test Suite")
    print("=" * 75)

    limiter.reset()

    with TestClient(app) as client:
        # Create test user
        db = SessionLocal()
        user_email = f"shoplook_{int(time.time())}@example.com"
        user = User(name="ShopLook User", email=user_email, password_hash=hash_password("Pass123!"), is_admin=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        token = client.post("/api/auth/login", json={"email": user_email, "password": "Pass123!"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # [Test 1] Backward Compatibility: Single-Item Search
        print("\n[1] Testing Existing Single-Item Image Search Backward Compatibility...")
        single_bytes = create_synthetic_garment_image((20, 20, 20))
        single_files = {"file": ("single_shirt.jpg", single_bytes, "image/jpeg")}
        single_res = client.post("/api/search/image", files=single_files, headers=headers)
        assert single_res.status_code == 200, f"Single search failed: {single_res.text}"
        single_data = single_res.json()
        assert "search_id" in single_data
        assert "detected_items" in single_data
        assert "best_matches" in single_data
        assert "items" in single_data and len(single_data["items"]) == 1
        print(f"    -> Single image search successful (Search ID: {single_data['search_id']}) (PASSED)")

        # [Test 2] Multi-Garment Outfit Search with Real DeepFashion Items
        print("\n[2] Testing Multi-Item Shop The Look with Outfit Garments (Shirt + Dress + Shoes)...")
        garment_1 = load_dataset_image("15970.jpg") or create_synthetic_garment_image((20, 40, 80)) # Shirt
        garment_2 = load_dataset_image("39716.jpg") or create_synthetic_garment_image((40, 60, 180)) # Dress
        garment_3 = load_dataset_image("9204.jpg") or create_synthetic_garment_image((10, 10, 10)) # Shoes

        multi_files = [
            ("files", ("crop_1_shirt.jpg", garment_1, "image/jpeg")),
            ("files", ("crop_2_dress.jpg", garment_2, "image/jpeg")),
            ("files", ("crop_3_shoes.jpg", garment_3, "image/jpeg")),
        ]

        t_start = time.perf_counter()
        multi_res = client.post("/api/search/multi-item", files=multi_files, headers=headers)
        total_time_ms = (time.perf_counter() - t_start) * 1000

        assert multi_res.status_code == 200, f"Multi-item search failed: {multi_res.text}"
        multi_data = multi_res.json()

        assert multi_data["total_items"] == 3, f"Expected 3 items, got {multi_data['total_items']}"
        assert len(multi_data["items"]) == 3
        print(f"    -> Multi-item search completed in {total_time_ms:.1f}ms for 3 outfit garments.")

        # [Test 3 & 4 & 5 & 6] Inspect Per-Crop Independent Classifications & Retrieval
        print("\n[3-6] Inspecting Independent Classifications, Embeddings & FAISS Retrievals per Item:")
        for idx, item in enumerate(multi_data["items"], start=1):
            attr = item["detected_attributes"]
            print(f"\n    Item #{item['item_id']}:")
            print(f"      - Crop File:  {item['crop_filename']}")
            print(f"      - Category:   {attr['category']} (Confidence: {attr['confidence']}%)")
            print(f"      - Attributes: Color: {attr['color']}, Pattern: {attr['pattern']}, Style: {attr['style']}, Gender: {attr['gender_category']}")
            print(f"      - Closest Matches: {len(item['best_matches'])} items retrieved")
            print(f"      - Affordable Alternatives: {len(item['affordable_alternatives'])} items")
            if item["best_matches"]:
                top_match = item["best_matches"][0]
                print(f"      - Top Match: '{top_match['product']['name']}' (Score: {top_match['scores']['overall_score']:.1f}%)")

            assert attr["category"] != "", "Category must be predicted"
            assert len(item["best_matches"]) > 0, "Must return product matches from FAISS"

        if multi_data.get("outfit_total_price"):
            print(f"\n    -> Total Complete Outfit Price: INR {multi_data['outfit_total_price']}")

        # [Test 7] Invalid / Corrupted Crop Handling
        print("\n[7] Testing Invalid/Corrupted Crop Rejection in Multi-Item Search...")
        corrupt_files = [
            ("files", ("crop_1.jpg", single_bytes, "image/jpeg")),
            ("files", ("crop_2_corrupted.jpg", b"Random Not A Real JPEG Content", "image/jpeg")),
        ]
        corrupt_res = client.post("/api/search/multi-item", files=corrupt_files, headers=headers)
        assert corrupt_res.status_code == 400, f"Expected 400 for corrupted crop, got {corrupt_res.status_code}"
        print("    -> Corrupted garment crop safely rejected with 400 Bad Request (PASSED)")

        # [Test 8] Authentication Enforcement
        print("\n[8] Testing Authentication Enforcement on Multi-Item Search...")
        unauth_res = client.post("/api/search/multi-item", files=multi_files)
        assert unauth_res.status_code == 401, f"Expected 401, got {unauth_res.status_code}"
        print("    -> Unauthenticated multi-item request safely rejected with 401 Unauthorized (PASSED)")

        # [Test 9] Rate Limiting Enforcement
        print("\n[9] Testing Rate Limiting Enforcement on Search...")
        limiter.reset()
        limit_hit = False
        rate_files = [("files", ("crop.jpg", single_bytes, "image/jpeg"))]
        for i in range(settings.RATE_LIMIT_SEARCH_PER_MINUTE + 5):
            r = client.post("/api/search/multi-item", files=rate_files, headers=headers)
            if r.status_code == 429:
                limit_hit = True
                break
        assert limit_hit, "Rate limiter should trigger 429 for search operations"
        print("    -> Search rate limiter triggered 429 Too Many Requests (PASSED)")

        limiter.reset()

        print("\n" + "=" * 75)
        print("   ALL TASK 8 SHOP THE LOOK MULTI-ITEM TESTS PASSED SUCCESSFULLY!")
        print("=" * 75)

if __name__ == "__main__":
    run_tests()
