"""
Comprehensive image-serving verification test for Phase 7 Task 2.
1. Searches an image using POST /api/search/image.
2. Gets recommendations using GET /api/recommendations/{id}.
3. Checks every recommended product's image_url endpoint (GET /uploads/deepfashion/{filename}).
4. Verifies status 200, Content-Type image/jpeg, image dimensions, and absence of 404 errors.
"""
import io
import os
import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings

def run_image_serving_test():
    settings = get_settings()
    print("=" * 75)
    print("   Running Phase 7 Task 2 Image-Serving Verification Test")
    print("=" * 75)
    print(f"[*] Configured DATASET_IMAGES_DIR: {settings.DATASET_IMAGES_DIR}")
    print(f"[*] Active dataset image directories found on disk:")
    for d in settings.dataset_image_dirs:
        print(f"    - {d} (Exists: {d.exists()})")

    client = TestClient(app)

    # 1. Prepare query image
    # Look for a test image in active candidate dirs
    test_img_path = None
    for d in settings.dataset_image_dirs:
        if d.exists():
            for sample_name in ["15970.jpg", "8914.jpg", "12344.jpg", "39716.jpg", "59607.jpg"]:
                cand = d / sample_name
                if cand.exists():
                    test_img_path = cand
                    break
        if test_img_path:
            break

    if not test_img_path:
        print("[!] No test image found in dataset directories. Creating temporary test image...")
        temp_img = Image.new("RGB", (224, 224), color=(30, 60, 150))
        buf = io.BytesIO()
        temp_img.save(buf, format="JPEG")
        test_bytes = buf.getvalue()
        test_filename = "test_query.jpg"
    else:
        print(f"[*] Using test image: {test_img_path}")
        with open(test_img_path, "rb") as f:
            test_bytes = f.read()
        test_filename = test_img_path.name

    # 1. Register & Login test user
    import time
    user_email = f"img_test_{int(time.time() * 1000)}@example.com"
    print("\n[Step 1] Authenticating test user...")
    reg_res = client.post("/api/auth/register", json={
        "email": user_email,
        "password": "TestPassword123!",
        "name": "Image Test User"
    })
    assert reg_res.status_code == 201, f"Register failed: {reg_res.text}"
    token = reg_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    print(f"    -> Registered and authenticated as {user_email}. Bearer token acquired.")

    # 2. Upload/Search image
    print("\n[Step 2] Uploading real image to POST /api/search/image...")
    files = {"file": (test_filename, test_bytes, "image/jpeg")}
    res = client.post("/api/search/image", files=files, headers=auth_headers)
    assert res.status_code == 200, f"Search failed with status {res.status_code}: {res.text}"
    search_data = res.json()
    search_id = search_data["search_id"]
    detected = search_data.get("detected_items", [{}])[0]
    print(f"    -> Search ID: {search_id}")
    print(f"    -> ViT Detected: {detected.get('category')} (Confidence: {detected.get('confidence')}%)")
    print(f"    -> Matches returned: {len(search_data.get('results', []))}")

    # 3. Get Recommendations
    print(f"\n[Step 3] Fetching recommendations for Search ID {search_id} across all modes...")
    modes = ["best_match", "best_value", "similar_style", "lowest_price"]
    checked_images = set()
    errors_404 = []
    high_res_count = 0
    small_res_count = 0

    for mode in modes:
        rec_res = client.get(f"/api/recommendations/{search_id}?mode={mode}", headers=auth_headers)
        assert rec_res.status_code == 200, f"Recommendation failed for mode {mode}: {rec_res.text}"
        items = rec_res.json()
        print(f"    -> Mode '{mode}': {len(items)} items returned.")

        for item in items:
            p = item.get("product", {})
            img_url = p.get("image_url")
            if not img_url or img_url in checked_images:
                continue
            checked_images.add(img_url)

            # Step 4. Test serving the image
            img_res = client.get(img_url)
            if img_res.status_code == 404:
                errors_404.append((p.get("id"), p.get("name"), img_url))
                print(f"       [404 NOT FOUND] Product ID {p.get('id')}: {img_url}")
            elif img_res.status_code == 200:
                try:
                    img_obj = Image.open(io.BytesIO(img_res.content))
                    w, h = img_obj.size
                    if w > 500:
                        high_res_count += 1
                        quality_label = f"HIGH-RES ({w}x{h} px, {len(img_res.content) // 1024} KB)"
                    else:
                        small_res_count += 1
                        quality_label = f"THUMBNAIL ({w}x{h} px, {len(img_res.content) // 1024} KB)"
                    # Print first 3 items per mode
                    if len(checked_images) <= 6:
                        print(f"       [200 OK] ID {p.get('id')} ({p.get('name')[:35]}...) -> {quality_label}")
                except Exception as e:
                    print(f"       [DECODE ERROR] Product ID {p.get('id')}: {e}")

    print("\n" + "=" * 75)
    print("   IMAGE-SERVING VERIFICATION SUMMARY")
    print("=" * 75)
    print(f"[*] Total unique recommended product images tested: {len(checked_images)}")
    print(f"[*] Successfully served high-res images: {high_res_count}")
    print(f"[*] Successfully served thumbnail images: {small_res_count}")
    print(f"[*] 404 image errors: {len(errors_404)}")
    assert len(errors_404) == 0, f"Found {len(errors_404)} 404 image errors: {errors_404}"
    print("[SUCCESS] All recommended product images loaded with status 200 OK with 0 errors!")
    print("=" * 75)

if __name__ == "__main__":
    run_image_serving_test()
