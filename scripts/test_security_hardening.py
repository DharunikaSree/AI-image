"""
Comprehensive security test suite for Phase 7 Task 6:
Security Hardening, Upload Validation & Rate Limiting.
"""
import io
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

def create_valid_image_bytes() -> bytes:
    img = Image.new("RGB", (224, 224), color=(40, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_tests():
    print("=" * 75)
    print("   Running Phase 7 Task 6 Security Hardening & Rate Limiting Test Suite")
    print("=" * 75)

    limiter.reset()

    with TestClient(app) as client:
        # Setup test users (Normal & Admin)
        db = SessionLocal()
        user_email = f"sec_user_{int(time.time())}@example.com"
        admin_email = f"sec_admin_{int(time.time())}@example.com"

        user = User(name="Sec User", email=user_email, password_hash=hash_password("SecPass123!"), is_admin=False)
        admin = User(name="Sec Admin", email=admin_email, password_hash=hash_password("SecPass123!"), is_admin=True)
        db.add(user)
        db.add(admin)
        db.commit()
        db.refresh(user)
        db.refresh(admin)
        db.close()

        user_token = client.post("/api/auth/login", json={"email": user_email, "password": "SecPass123!"}).json()["access_token"]
        admin_token = client.post("/api/auth/login", json={"email": admin_email, "password": "SecPass123!"}).json()["access_token"]

        user_headers = {"Authorization": f"Bearer {user_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # [Test 1] Security Headers Verification
        print("\n[1] Testing Security Response Headers...")
        health_res = client.get("/api/health")
        assert health_res.headers.get("x-content-type-options") == "nosniff", "Missing X-Content-Type-Options"
        assert health_res.headers.get("x-frame-options") == "DENY", "Missing X-Frame-Options"
        assert health_res.headers.get("x-xss-protection") == "1; mode=block", "Missing X-XSS-Protection"
        assert "referrer-policy" in health_res.headers, "Missing Referrer-Policy"
        print("    -> Security headers present: nosniff, DENY, 1; mode=block, strict-origin (PASSED)")

        # [Test 2] Unauthenticated Protected Endpoint Rejection
        print("\n[2] Testing Unauthenticated Protected Endpoint Rejection...")
        unauth_search = client.post("/api/search/image")
        assert unauth_search.status_code == 401, f"Expected 401, got {unauth_search.status_code}"
        unauth_history = client.get("/api/history")
        assert unauth_history.status_code == 401
        print("    -> Unauthenticated requests strictly rejected with 401 Unauthorized (PASSED)")

        # [Test 3] Non-Admin Accessing Admin Endpoints Rejection
        print("\n[3] Testing Non-Admin User Accessing Admin Endpoints...")
        forbidden_admin = client.get("/api/admin/products", headers=user_headers)
        assert forbidden_admin.status_code == 403, f"Expected 403, got {forbidden_admin.status_code}"
        print("    -> Non-admin user access strictly rejected with 403 Forbidden (PASSED)")

        # [Test 4] Oversized File Upload Rejection
        print("\n[4] Testing Oversized File Upload Protection...")
        oversized_bytes = b"0" * ((settings.MAX_UPLOAD_MB + 1) * 1024 * 1024)
        over_files = {"file": ("big_image.jpg", oversized_bytes, "image/jpeg")}
        over_res = client.post("/api/search/image", files=over_files, headers=user_headers)
        assert over_res.status_code == 400, f"Expected 400 for oversized file, got {over_res.status_code}"
        assert f"{settings.MAX_UPLOAD_MB}MB" in over_res.json()["detail"]
        print(f"    -> Upload exceeding {settings.MAX_UPLOAD_MB}MB rejected with 400 Bad Request (PASSED)")

        # [Test 5] Invalid File Extension Rejection
        print("\n[5] Testing Invalid File Extension Rejection...")
        fake_files = {"file": ("script.sh", b"#!/bin/bash\necho hello", "text/plain")}
        bad_ext_res = client.post("/api/search/image", files=fake_files, headers=user_headers)
        assert bad_ext_res.status_code == 400, f"Expected 400 for invalid extension, got {bad_ext_res.status_code}"
        print("    -> Non-image file extensions rejected with 400 Bad Request (PASSED)")

        # [Test 6] Corrupted Image Content / Magic Byte Verification
        print("\n[6] Testing Corrupted/Spoofed Image Content Verification...")
        # File named .jpg but containing invalid random bytes (e.g. payload masquerading as jpg)
        corrupted_bytes = b"This is not a real JPEG image binary content header."
        corrupted_files = {"file": ("spoofed.jpg", corrupted_bytes, "image/jpeg")}
        corrupted_res = client.post("/api/search/image", files=corrupted_files, headers=user_headers)
        assert corrupted_res.status_code == 400, f"Expected 400 for corrupted image, got {corrupted_res.status_code}"
        print("    -> Spoofed/corrupted image content strictly rejected via PIL magic byte verification (PASSED)")

        # [Test 7] Path Traversal Attack Defense
        print("\n[7] Testing Path Traversal Defense on Image Serving...")
        traversal_attempts = [
            "../../etc/passwd",
            "..\\..\\Windows\\win.ini",
            "..%2F..%2Fsecret.txt",
            "/absolute/path/test.jpg",
            "....//....//config.py",
        ]
        for payload in traversal_attempts:
            trav_res = client.get(f"/uploads/deepfashion/{payload}")
            assert trav_res.status_code in (400, 404), f"Traversal '{payload}' returned {trav_res.status_code}"
        print("    -> Path traversal attempts safely rejected with 400/404 without disk disclosure (PASSED)")

        # [Test 8] Valid Authenticated Search
        print("\n[8] Testing Valid Authenticated Search with Real JPEG...")
        valid_bytes = create_valid_image_bytes()
        valid_files = {"file": ("clean_fashion_query.jpg", valid_bytes, "image/jpeg")}
        valid_res = client.post("/api/search/image", files=valid_files, headers=user_headers)
        assert valid_res.status_code == 200, f"Valid search failed: {valid_res.text}"
        search_data = valid_res.json()
        assert "detected_items" in search_data and "best_matches" in search_data
        print(f"    -> Legitimate search succeeded. Result matches: {len(search_data['best_matches'])} (PASSED)")

        # [Test 9] Valid Admin Catalog Access
        print("\n[9] Testing Valid Admin Catalog Access...")
        admin_res = client.get("/api/admin/products?limit=5", headers=admin_headers)
        assert admin_res.status_code == 200
        assert len(admin_res.json()["items"]) == 5
        print("    -> Admin access authorized and verified (PASSED)")

        # [Test 10] Rate Limiting Enforcement
        print("\n[10] Testing Rate Limiting Enforcement (Auth Endpoint)...")
        # Trigger auth rate limit by sending requests rapidly
        limiter.reset()
        limit_triggered = False
        retry_val = None
        for i in range(settings.RATE_LIMIT_AUTH_PER_MINUTE + 5):
            res = client.post("/api/auth/login", json={"email": "wrong@example.com", "password": "WrongPassword!"})
            if res.status_code == 429:
                limit_triggered = True
                retry_val = res.headers.get("retry-after")
                break

        assert limit_triggered, f"Rate limiter failed to trigger 429 after {settings.RATE_LIMIT_AUTH_PER_MINUTE} attempts"
        assert retry_val is not None, "429 response must include Retry-After header"
        print(f"    -> Rate limiter triggered 429 Too Many Requests (Retry-After: {retry_val}s) (PASSED)")

        # Reset limiter for subsequent tests
        limiter.reset()

        print("\n" + "=" * 75)
        print("   ALL TASK 6 SECURITY HARDENING & RATE LIMITING CHECKS PASSED!")
        print("=" * 75)

if __name__ == "__main__":
    run_tests()
