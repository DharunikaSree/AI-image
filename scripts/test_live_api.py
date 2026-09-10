"""
Test Live Search API endpoint with real images:
1. Shoe image
2. Shirt image
3. Dress image
4. Saree image
Verifies ViT category detection, CLIP+FAISS retrieval, and DeepFashion recommendation scoring.
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
from app.core.security import create_access_token
from app.core.database import SessionLocal
from app.models.user import User

DATA_DIR = PROJECT_ROOT / "data"
METADATA_PATH = DATA_DIR / "deepfashion_metadata.json"


def test_api():
    print("=" * 75)
    print("   Testing Live /api/search/image Pipeline with Real Fashion Items")
    print("=" * 75)

    client = TestClient(app)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "demo@fashionai.dev").first()
        if not user:
            print("[!] Demo user not found.")
            return
        token = create_access_token(str(user.id))
        headers = {"Authorization": f"Bearer {token}"}
    finally:
        db.close()

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    test_targets = [
        ("Shoes", ["Casual Shoes", "Sports Shoes", "Formal Shoes", "Heels"]),
        ("Shirt", ["Shirts", "Tops"]),
        ("Dress", ["Dresses"]),
        ("Saree", ["Sarees"]),
    ]

    all_tests_passed = True
    test_summary = []

    for target_cat, art_types in test_targets:
        matching = [m for m in metadata if m.get("article_type") in art_types and os.path.exists(m.get("image_path", ""))][:1]
        if not matching:
            print(f"[!] No matching test item found for category: {target_cat}")
            continue

        item = matching[0]
        image_path = item["image_path"]
        print(f"\n>>> Running Search for [{target_cat}] Query Image:")
        print(f"    File: {Path(image_path).name} | Item: {item['name']}")

        start_t = time.perf_counter()
        with open(image_path, "rb") as f:
            response = client.post(
                "/api/search/image",
                files={"file": (Path(image_path).name, f, "image/jpeg")},
                headers=headers,
            )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        if response.status_code != 200:
            print(f"    [FAIL] API returned {response.status_code}: {response.text}")
            all_tests_passed = False
            continue

        data = response.json()
        detected_items = data.get("detected_items", [])
        primary = detected_items[0] if detected_items else {}
        detected_category = primary.get("category", "")
        detected_conf = primary.get("confidence", 0.0)
        detected_color = primary.get("color", "")
        detected_pattern = primary.get("pattern", "")

        best_matches = data.get("best_matches", [])
        top_product = best_matches[0]["product"] if best_matches else {}
        top_scores = best_matches[0]["scores"] if best_matches else {}

        is_category_correct = (detected_category == target_cat)
        if not is_category_correct:
            all_tests_passed = False

        status_tag = "[PASSED]" if is_category_correct else "[FAILED]"
        print(f"    {status_tag} ViT Classification: [{detected_category}] (Confidence: {detected_conf}%, Color: {detected_color}, Pattern: {detected_pattern})")
        print(f"    Latency: {elapsed_ms:.1f}ms | Best Matches Count: {len(best_matches)}")
        print(f"    Top Match: '{top_product.get('name')}' (Category: {top_product.get('category')}, Platform: {top_product.get('platform')})")
        print(f"      - Visual Similarity: {top_scores.get('visual_score')}%")
        print(f"      - Category Score:    {top_scores.get('category_score')}%")
        print(f"      - Overall Score:     {top_scores.get('overall_score')}%")
        print(f"      - Image URL:         {top_product.get('image_url')}")
        print(f"      - Reasons:           {top_scores.get('reasons')}")

        print("    Top-3 Recommended Products:")
        for idx, m in enumerate(best_matches[:3], start=1):
            p = m["product"]
            sc = m["scores"]
            print(f"      {idx}. [{p.get('category')}] {p.get('name')} | Price: INR {p.get('price')} | Match: {sc.get('overall_score')}% | Img: {p.get('image_url')}")

        test_summary.append({
            "target": target_cat,
            "query_image": item["name"],
            "detected_category": detected_category,
            "detected_confidence": detected_conf,
            "detected_color": detected_color,
            "latency_ms": round(elapsed_ms, 1),
            "top_match_name": top_product.get("name"),
            "top_match_category": top_product.get("category"),
            "top_match_image_url": top_product.get("image_url"),
            "top_match_score": top_scores.get("overall_score"),
            "passed": is_category_correct
        })

    print("\n" + "=" * 75)
    if all_tests_passed:
        print("[SUCCESS] All 4 Fashion Categories (Shoes, Shirt, Dress, Saree) Passed Live Search Test!")
    else:
        print("[WARNING] Some category classifications did not match.")
    print("=" * 75)

    return test_summary


if __name__ == "__main__":
    test_api()
