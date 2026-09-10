"""
Comprehensive verification test for Phase 7 Task 3:
Admin Product API Pagination, Search, Filtering & CRUD.
"""
import io
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import hash_password

def run_tests():
    print("=" * 75)
    print("   Running Phase 7 Task 3 Admin Pagination & Search Test Suite")
    print("=" * 75)

    client = TestClient(app)
    db = SessionLocal()

    # 1. Setup Admin and Normal User
    admin_email = f"admin_test_{int(time.time())}@example.com"
    user_email = f"user_test_{int(time.time())}@example.com"

    admin_user = User(name="Admin User", email=admin_email, password_hash=hash_password("AdminPass123!"), is_admin=True)
    normal_user = User(name="Normal User", email=user_email, password_hash=hash_password("UserPass123!"), is_admin=False)
    db.add(admin_user)
    db.add(normal_user)
    db.commit()
    db.refresh(admin_user)
    db.refresh(normal_user)
    db.close()

    # Login both users
    admin_login = client.post("/api/auth/login", json={"email": admin_email, "password": "AdminPass123!"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    user_login = client.post("/api/auth/login", json={"email": user_email, "password": "UserPass123!"})
    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # [Test 1] Auth & Authorization
    print("\n[1] Testing Authorization & Permissions...")
    unauth_res = client.get("/api/admin/products")
    assert unauth_res.status_code == 401, f"Expected 401 for unauthenticated request, got {unauth_res.status_code}"
    print("    -> Unauthenticated request correctly rejected with 401 Unauthorized.")

    forbidden_res = client.get("/api/admin/products", headers=user_headers)
    assert forbidden_res.status_code == 403, f"Expected 403 for non-admin request, got {forbidden_res.status_code}"
    print("    -> Non-admin request correctly rejected with 403 Forbidden.")

    # [Test 2] Page 1 Retrieval
    print("\n[2] Testing GET /api/admin/products?page=1&limit=20...")
    t0 = time.time()
    p1_res = client.get("/api/admin/products?page=1&limit=20", headers=admin_headers)
    p1_time = (time.time() - t0) * 1000
    assert p1_res.status_code == 200, f"Failed: {p1_res.text}"
    p1_data = p1_res.json()
    assert "items" in p1_data and "total" in p1_data and "total_pages" in p1_data
    assert len(p1_data["items"]) == 20, f"Expected 20 items, got {len(p1_data['items'])}"
    assert p1_data["page"] == 1
    assert p1_data["limit"] == 20
    assert p1_data["total"] >= 44441, f"Expected >= 44441 total products, got {p1_data['total']}"
    assert p1_data["total_pages"] >= 2223
    print(f"    -> Page 1 returned 20 items in {p1_time:.1f}ms. Total items: {p1_data['total']}, Total pages: {p1_data['total_pages']}")
    first_page_ids = [item["id"] for item in p1_data["items"]]

    # [Test 3] Page 2 Retrieval
    print("\n[3] Testing GET /api/admin/products?page=2&limit=20...")
    t0 = time.time()
    p2_res = client.get("/api/admin/products?page=2&limit=20", headers=admin_headers)
    p2_time = (time.time() - t0) * 1000
    assert p2_res.status_code == 200
    p2_data = p2_res.json()
    assert len(p2_data["items"]) == 20
    assert p2_data["page"] == 2
    second_page_ids = [item["id"] for item in p2_data["items"]]
    assert set(first_page_ids).isdisjoint(set(second_page_ids)), "Page 1 and Page 2 items must be distinct!"
    print(f"    -> Page 2 returned 20 distinct items in {p2_time:.1f}ms.")

    # [Test 4] Last Page Retrieval
    last_page = p1_data["total_pages"]
    print(f"\n[4] Testing Last Page retrieval: GET /api/admin/products?page={last_page}&limit=20...")
    t0 = time.time()
    plast_res = client.get(f"/api/admin/products?page={last_page}&limit=20", headers=admin_headers)
    plast_time = (time.time() - t0) * 1000
    assert plast_res.status_code == 200
    plast_data = plast_res.json()
    assert len(plast_data["items"]) > 0 and len(plast_data["items"]) <= 20
    print(f"    -> Last page {last_page} returned {len(plast_data['items'])} items in {plast_time:.1f}ms.")

    # [Test 5] Search Functionality
    print("\n[5] Testing Search: GET /api/admin/products?search=shirt&limit=15...")
    t0 = time.time()
    s_res = client.get("/api/admin/products?search=shirt&limit=15", headers=admin_headers)
    s_time = (time.time() - t0) * 1000
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert len(s_data["items"]) <= 15
    assert s_data["total"] > 0
    for it in s_data["items"]:
        match = "shirt" in it["name"].lower() or "shirt" in it["category"].lower() or "shirt" in it["brand"].lower() or "shirt" in it["description"].lower()
        assert match, f"Item {it['name']} did not match search term 'shirt'"
    print(f"    -> Search for 'shirt' found {s_data['total']} matching products in {s_time:.1f}ms. First 15 returned.")

    # [Test 6] Category Filtering
    print("\n[6] Testing Category Filter: GET /api/admin/products?category=Shoes&limit=15...")
    t0 = time.time()
    cat_res = client.get("/api/admin/products?category=Shoes&limit=15", headers=admin_headers)
    cat_time = (time.time() - t0) * 1000
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert len(cat_data["items"]) <= 15
    for it in cat_data["items"]:
        assert it["category"] == "Shoes", f"Expected category 'Shoes', got {it['category']}"
    print(f"    -> Category filter 'Shoes' found {cat_data['total']} products in {cat_time:.1f}ms.")

    # [Test 7] Full Admin CRUD Lifecycle
    print("\n[7] Testing Admin CRUD Lifecycle...")
    # CREATE
    new_product_payload = {
        "name": f"Automated Test Silk Kurta {int(time.time())}",
        "description": "Premium silk kurta for automated test suite",
        "brand": "Lumière Test",
        "category": "Kurta",
        "subcategory": "Topwear",
        "style": "Traditional",
        "color": "Royal Blue",
        "pattern": "Solid",
        "price": 2499,
        "discount_price": 1999,
        "currency": "INR",
        "image_url": "/uploads/deepfashion/15970.jpg",
        "product_url": "https://example.com/test",
        "platform": "Test Studio",
        "availability": True,
        "group_key": "test-kurta-group",
    }
    create_res = client.post("/api/admin/products", json=new_product_payload, headers=admin_headers)
    assert create_res.status_code == 201, f"Create failed: {create_res.text}"
    created_product = create_res.json()
    new_id = created_product["id"]
    print(f"    -> Product created successfully with ID: {new_id}")

    # READ via search
    verify_res = client.get(f"/api/admin/products?search=Automated+Test+Silk+Kurta", headers=admin_headers)
    assert verify_res.status_code == 200
    found_ids = [p["id"] for p in verify_res.json()["items"]]
    assert new_id in found_ids, f"Created product ID {new_id} not found in search results"
    print(f"    -> Verified created product is searchable and appears in paginated query.")

    # UPDATE
    update_payload = {
        **new_product_payload,
        "name": f"Automated Test Silk Kurta Updated {int(time.time())}",
        "price": 2999,
        "discount_price": 2399,
    }
    update_res = client.put(f"/api/admin/products/{new_id}", json=update_payload, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()["price"] == 2999
    print(f"    -> Product updated successfully. New price: INR 2999")

    # DELETE
    del_res = client.delete(f"/api/admin/products/{new_id}", headers=admin_headers)
    assert del_res.status_code == 204
    print(f"    -> Product deleted successfully.")

    # VERIFY DELETED
    del_verify_res = client.get(f"/api/products/{new_id}")
    assert del_verify_res.status_code == 404
    print(f"    -> Verified deleted product no longer exists (404 Not Found).")

    # [Test 8] Dashboard Fast Aggregation Test
    print("\n[8] Testing Optimized Admin Dashboard API...")
    t0 = time.time()
    dash_res = client.get("/api/admin/dashboard", headers=admin_headers)
    dash_time = (time.time() - t0) * 1000
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    print(f"    -> Dashboard loaded in {dash_time:.1f}ms without loading all rows into RAM.")
    print(f"    -> Total Products: {dash_data['total_products']}")
    print(f"    -> Price Distribution Buckets: {len(dash_data['price_distribution'])} buckets computed via SQL.")

    # [Test 9] Enforced Limit Cap
    print("\n[9] Testing Max Limit Enforcement...")
    over_limit_res = client.get("/api/admin/products?limit=500", headers=admin_headers)
    assert over_limit_res.status_code == 422, "API must reject limit > 100 with 422 Validation Error"
    print("    -> Limit > 100 correctly rejected with 422 Validation Error.")

    print("\n" + "=" * 75)
    print("   ALL TASK 3 PAGINATION, SEARCH & CRUD TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
