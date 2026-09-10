"""
Comprehensive verification test for Phase 6 improvements.
Tests all 10 endpoint workflows:
1. GET /api/health
2. POST /api/auth/register (or test account)
3. POST /api/auth/login
4. Bearer token auth headers
5. POST /api/search/image (verifying ai_mode == 'model' and valid detected attributes)
6. GET /api/search/{search_id}
7. GET /api/recommendations/{search_id} (verifying non-zero visual_score values)
8. GET /api/products
9. GET /api/profile
10. GET /api/history
"""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app

DATA_DIR = PROJECT_ROOT / "data"
METADATA_PATH = DATA_DIR / "deepfashion_metadata.json"

def run_all_tests():
    print("=" * 75)
    print("   Running Comprehensive Phase 6 Verification Test Suite")
    print("=" * 75)

    client = TestClient(app)
    results = {}

    # 1. GET /api/health
    print("\n[1] Testing GET /api/health...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f"    -> Status: {res.status_code} | Body: {health_data}")
    assert health_data.get("status") == "ok"
    assert health_data.get("ai_mode") == "model", f"Expected ai_mode 'model', got '{health_data.get('ai_mode')}'"
    results["health"] = "PASSED"

    # 2. POST /api/auth/register & 3. POST /api/auth/login
    print("\n[2 & 3] Testing Auth endpoints (register / login)...")
    test_email = f"phase6_tester_{int(time.time())}@fashionai.dev"
    reg_res = client.post("/api/auth/register", json={
        "name": "Phase 6 Tester",
        "email": test_email,
        "password": "Password123!"
    })
    print(f"    -> Register status: {reg_res.status_code}")
    assert reg_res.status_code in (200, 201), f"Register failed: {reg_res.text}"

    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "Password123!"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    token = token_data.get("access_token")
    print(f"    -> Login status: 200 | Token generated: {token[:20]}...")
    results["auth"] = "PASSED"

    # 4. Bearer token headers
    headers = {"Authorization": f"Bearer {token}"}

    # 5. POST /api/search/image with real fashion image
    print("\n[5] Testing POST /api/search/image with real fashion item...")
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    test_item = next(m for m in metadata if m.get("category") in ("Dress", "Shirt", "Shoes") and os.path.exists(m.get("image_path", "")))
    image_path = test_item["image_path"]
    print(f"    -> Using test image: {test_item['name']} ({image_path})")

    with open(image_path, "rb") as f:
        search_res = client.post(
            "/api/search/image",
            files={"file": (Path(image_path).name, f, "image/jpeg")},
            headers=headers,
        )
    assert search_res.status_code == 200, f"Search failed: {search_res.text}"
    search_data = search_res.json()
    search_id = search_data["search_id"]
    ai_mode = search_data.get("ai_mode")
    detected = search_data["detected_items"][0]
    best_matches = search_data["best_matches"]

    print(f"    -> Search ID: {search_id}")
    print(f"    -> AI Mode in response: '{ai_mode}'")
    print(f"    -> Detected: {detected['category']} (Confidence: {detected['confidence']}%, Color: {detected['color']})")
    print(f"    -> Matches returned: {len(best_matches)}")
    assert ai_mode == "model", f"Expected ai_mode 'model', got '{ai_mode}'"
    assert len(best_matches) > 0
    results["search_by_image"] = "PASSED"

    # 6. GET /api/search/{search_id}
    print(f"\n[6] Testing GET /api/search/{search_id}...")
    get_search_res = client.get(f"/api/search/{search_id}", headers=headers)
    assert get_search_res.status_code == 200, f"Get search history item failed: {get_search_res.text}"
    history_item = get_search_res.json()
    print(f"    -> Retrieved history item ID: {history_item['id']} | Category: {history_item['detected_category']}")
    assert history_item["id"] == search_id
    results["get_search"] = "PASSED"

    # 7. GET /api/recommendations/{search_id} (Checking non-zero visual scores)
    print(f"\n[7] Testing GET /api/recommendations/{search_id}...")
    rec_modes = ["best_match", "best_value", "similar_style", "lowest_price"]
    for mode in rec_modes:
        rec_res = client.get(f"/api/recommendations/{search_id}?mode={mode}", headers=headers)
        assert rec_res.status_code == 200, f"Get recommendations ({mode}) failed: {rec_res.text}"
        recs = rec_res.json()
        print(f"    -> Mode '{mode}': {len(recs)} items returned.")
        assert len(recs) > 0
        top_rec = recs[0]
        top_scores = top_rec["scores"]
        print(f"       Top item: '{top_rec['product']['name']}' | Visual Score: {top_scores['visual_score']}% | Overall: {top_scores['overall_score']}%")
        assert top_scores["visual_score"] > 0, f"visual_score is 0 for mode {mode}!"
    results["recommendations_visual_score"] = "PASSED"

    # 8. GET /api/products
    print("\n[8] Testing GET /api/products...")
    prod_res = client.get("/api/products?limit=10")
    assert prod_res.status_code == 200, f"Get products failed: {prod_res.text}"
    prods = prod_res.json()
    print(f"    -> Retrieved {len(prods)} products from catalog.")
    assert len(prods) > 0
    results["get_products"] = "PASSED"

    # 9. GET /api/profile
    print("\n[9] Testing GET /api/profile...")
    prof_res = client.get("/api/profile", headers=headers)
    assert prof_res.status_code == 200, f"Get profile failed: {prof_res.text}"
    prof = prof_res.json()
    print(f"    -> User: {prof.get('name')} | Email: {prof.get('email')}")
    results["get_profile"] = "PASSED"

    # 10. GET /api/history
    print("\n[10] Testing GET /api/history...")
    hist_res = client.get("/api/history", headers=headers)
    assert hist_res.status_code == 200, f"Get history failed: {hist_res.text}"
    hist = hist_res.json()
    print(f"    -> User search history count: {len(hist)}")
    assert len(hist) > 0
    results["get_history"] = "PASSED"

    print("\n" + "=" * 75)
    print("   ALL 10 PHASE 6 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 75)
    for test_name, status in results.items():
        print(f"   [x] {test_name.ljust(30)} : {status}")

if __name__ == "__main__":
    run_all_tests()
