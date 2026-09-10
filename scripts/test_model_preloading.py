"""
Comprehensive verification test for Phase 7 Task 5:
AI Model Preloading & Cold-Start Elimination.
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
from app.models.user import User
from app.core.security import hash_password

settings = get_settings()

def create_dummy_image_bytes() -> bytes:
    img = Image.new("RGB", (224, 224), color=(30, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_tests():
    print("=" * 75)
    print("   Running Phase 7 Task 5 AI Model Preloading & Latency Test Suite")
    print("=" * 75)

    print("\n[1] Initializing FastAPI TestClient with Lifespan Context...")
    t0 = time.time()
    with TestClient(app) as client:
        boot_time = (time.time() - t0) * 1000
        print(f"    -> Server booted and models preloaded in {boot_time:.1f}ms.")

        # [Test 1] Health Endpoint Diagnostics
        print("\n[2] Checking GET /api/health for Preloaded Model Status...")
        health_res = client.get("/api/health")
        assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
        data = health_res.json()
        print(f"    -> Response: {data}")

        assert data["status"] == "ok"
        assert "models" in data, "Health response must include 'models' diagnostic dictionary"
        models_status = data["models"]

        if settings.AI_MODE == "model":
            assert models_status["vit_classifier"] is True, "ViT classifier must be loaded on startup"
            print("    -> ViT Fashion Classifier: PRELOADED & WARM (PASSED)")

        assert models_status["clip_model"] is True, "CLIP Model must be loaded on startup"
        print("    -> CLIP Vision Transformer: PRELOADED & WARM (PASSED)")

        assert models_status["faiss_index"] is True, "FAISS Index must be loaded on startup"
        assert models_status["faiss_vectors"] >= 44441, f"Expected >= 44441 vectors, got {models_status['faiss_vectors']}"
        print(f"    -> FAISS Vector Index: PRELOADED ({models_status['faiss_vectors']} vectors synchronized) (PASSED)")

        # Setup user for search test
        db = SessionLocal()
        test_email = f"preload_test_{int(time.time())}@example.com"
        user = User(name="Preload Test User", email=test_email, password_hash=hash_password("Pass1234!"))
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        login_res = client.post("/api/auth/login", json={"email": test_email, "password": "Pass1234!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # [Test 2] First-Query Latency Benchmark
        print("\n[3] Benchmarking Query #1 (First User Visual Search)...")
        img_bytes = create_dummy_image_bytes()
        files = {"file": ("test_warm_query1.jpg", img_bytes, "image/jpeg")}

        t_search0 = time.time()
        search_res1 = client.post("/api/search/image", files=files, headers=headers)
        search_time1 = (time.time() - t_search0) * 1000

        assert search_res1.status_code == 200, f"Search 1 failed: {search_res1.text}"
        res1_data = search_res1.json()
        print(f"    -> Search Query #1 completed in {search_time1:.1f}ms.")
        print(f"    -> Detected: {res1_data['detected_items'][0]['category']} ({res1_data['detected_items'][0]['confidence']}%)")
        print(f"    -> Best Matches: {len(res1_data['best_matches'])} items retrieved.")
        assert search_time1 < 1000.0, f"Cold-start latency too high ({search_time1:.1f}ms). Must be < 1000ms."

        # [Test 3] Subsequent Query Latency Benchmark
        print("\n[4] Benchmarking Query #2 (Subsequent Visual Search)...")
        files2 = {"file": ("test_warm_query2.jpg", img_bytes, "image/jpeg")}
        t_search1 = time.time()
        search_res2 = client.post("/api/search/image", files=files2, headers=headers)
        search_time2 = (time.time() - t_search1) * 1000

        assert search_res2.status_code == 200
        print(f"    -> Search Query #2 completed in {search_time2:.1f}ms.")

        print("\n" + "=" * 75)
        print("   ALL TASK 5 MODEL PRELOADING & WARMUP TESTS PASSED SUCCESSFULLY!")
        print("=" * 75)

if __name__ == "__main__":
    run_tests()
