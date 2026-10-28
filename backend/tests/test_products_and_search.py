import io

from PIL import Image


def make_test_image_bytes(color=(200, 40, 40), size=(200, 250)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def test_list_products_empty_catalog(client):
    res = client.get("/api/products")
    assert res.status_code == 200
    assert res.json() == []


def test_get_missing_product_404(client):
    res = client.get("/api/products/9999")
    assert res.status_code == 404


def test_image_search_rejects_unsupported_format(client, auth_headers):
    res = client.post(
        "/api/search/image",
        headers=auth_headers,
        files={"file": ("photo.txt", b"not an image", "text/plain")},
    )
    assert res.status_code == 400


def test_image_search_rejects_empty_file(client, auth_headers):
    res = client.post(
        "/api/search/image",
        headers=auth_headers,
        files={"file": ("photo.jpg", b"", "image/jpeg")},
    )
    assert res.status_code == 400


def test_image_search_accepts_valid_image_and_returns_detected_attributes(client, auth_headers):
    img_bytes = make_test_image_bytes()
    res = client.post(
        "/api/search/image",
        headers=auth_headers,
        files={"file": ("photo.jpg", img_bytes, "image/jpeg")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_mode"] in ("demo", "model")
    assert len(body["detected_items"]) == 1
    assert body["detected_items"][0]["category"]
    assert body["detected_items"][0]["confidence"] > 0


def test_image_search_requires_auth(client):
    img_bytes = make_test_image_bytes()
    res = client.post("/api/search/image", files={"file": ("photo.jpg", img_bytes, "image/jpeg")})
    assert res.status_code == 401


def test_demo_classifier_is_deterministic():
    """Same image bytes must always produce the same category/color (not random)."""
    import tempfile
    from app.services.ai_classifier import classify_image

    img_bytes = make_test_image_bytes(color=(30, 30, 30))
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(img_bytes)
        path = f.name

    first = classify_image(path)
    second = classify_image(path)
    assert first[0].category == second[0].category
    assert first[0].color == second[0].color
    assert first[0].confidence == second[0].confidence


def test_product_detail_returns_external_links_schema(client, auth_headers):
    """Verifies that Product Details API returns external_links list and backward-compatible fields."""
    from app.core.database import SessionLocal
    from app.models.product import Product, ProductExternalLink

    db = SessionLocal()
    try:
        p = Product(
            name="Test Silk Shirt",
            brand="Heritage Loom",
            category="Shirt",
            price=1999.0,
            image_url="/uploads/test.jpg",
            product_url="",
            platform="DeepFashion",
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        # 1. Test when no external links exist -> returns external_links: []
        res = client.get(f"/api/products/{p.id}")
        assert res.status_code == 200
        data = res.json()
        assert "external_links" in data
        assert data["external_links"] == []
        assert data["product_url"] == ""

        # 2. Add verified external link
        link = ProductExternalLink(
            product_id=p.id,
            store_name="Myntra",
            external_url="https://www.myntra.com/shirts/heritage-loom/1",
            verification_status="verified",
            availability_status="in_stock",
        )
        db.add(link)
        db.commit()

        res = client.get(f"/api/products/{p.id}")
        assert res.status_code == 200
        data = res.json()
        assert len(data["external_links"]) == 1
        link_data = data["external_links"][0]
        assert link_data["store_name"] == "Myntra"
        assert link_data["url"] == "https://www.myntra.com/shirts/heritage-loom/1"
        assert link_data["verification_status"] == "verified"
        assert link_data["availability_status"] == "available"
    finally:
        db.close()


def test_delete_history_cascade_and_image_cleanup(client):
    """P4 Test: Verify deleting history record cascades to Recommendation/SearchResult and cleans up image."""
    from pathlib import Path
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import Recommendation, SearchHistory, SearchResult
    from app.models.product import Product
    from app.models.user import User

    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    test_filename = "test_p4_cleanup.jpg"
    test_file_path = upload_dir / test_filename
    test_file_path.write_bytes(b"dummy image bytes for p4 test")
    assert test_file_path.exists()

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_p4@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        prod = Product(name="Test Cascade Prod", category="Shirt", price=500.0)
        db.add(prod)
        db.commit()

        search = SearchHistory(
            user_id=user.id,
            image_path=f"uploads/{test_filename}",
            detected_category="Shirt",
        )
        db.add(search)
        db.commit()

        # Add child SearchResult and child Recommendation
        sr = SearchResult(search_id=search.id, product_id=prod.id, similarity_score=90.0)
        rec = Recommendation(search_id=search.id, product_id=prod.id, mode="best_match", overall_score=90.0)
        db.add_all([sr, rec])
        db.commit()

        search_id = search.id
        assert db.query(SearchResult).filter(SearchResult.search_id == search_id).count() == 1
        assert db.query(Recommendation).filter(Recommendation.search_id == search_id).count() == 1

        # Delete history via user_routes endpoint
        res = client.delete(f"/api/history/{search_id}", headers=headers)
        assert res.status_code == 204

        # Verify cascades: SearchHistory, SearchResult, and Recommendation must all be deleted
        assert db.query(SearchHistory).filter(SearchHistory.id == search_id).first() is None
        assert db.query(SearchResult).filter(SearchResult.search_id == search_id).count() == 0
        assert db.query(Recommendation).filter(Recommendation.search_id == search_id).count() == 0

        # Verify image cleanup: file on disk was unlinked
        assert not test_file_path.exists()
    finally:
        if test_file_path.exists():
            test_file_path.unlink()
        db.close()


def test_delete_history_preserves_shared_image(client):
    """P4 Test: Verify image is not deleted if another search history record references it."""
    from pathlib import Path
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import SearchHistory
    from app.models.user import User

    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    shared_filename = "test_shared_image.jpg"
    shared_path = upload_dir / shared_filename
    shared_path.write_bytes(b"shared image content")

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_shared@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        s1 = SearchHistory(user_id=user.id, image_path=f"uploads/{shared_filename}", detected_category="Shirt")
        s2 = SearchHistory(user_id=user.id, image_path=f"uploads/{shared_filename}", detected_category="Shirt")
        db.add_all([s1, s2])
        db.commit()

        # Delete first search
        res1 = client.delete(f"/api/history/{s1.id}", headers=headers)
        assert res1.status_code == 204
        # File must STILL exist because s2 references it
        assert shared_path.exists()

        # Delete second search
        res2 = client.delete(f"/api/history/{s2.id}", headers=headers)
        assert res2.status_code == 204
        # File must NOW be deleted because no other record references it
        assert not shared_path.exists()
    finally:
        if shared_path.exists():
            shared_path.unlink()
        db.close()


def test_delete_history_handles_missing_files_and_path_safety(client):
    """P4 Test: Missing files or traversal paths do not cause errors or delete outside UPLOAD_DIR."""
    from pathlib import Path
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import SearchHistory
    from app.models.user import User

    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Canary file outside upload dir to ensure path traversal safety
    canary_file = upload_dir.parent / "p4_canary.txt"
    canary_file.write_text("must never be deleted")

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_safety@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        # 1. Non-existent file
        s_missing = SearchHistory(user_id=user.id, image_path="uploads/non_existent_12345.jpg", detected_category="Dress")
        # 2. Path traversal attempt
        s_traversal = SearchHistory(user_id=user.id, image_path="../p4_canary.txt", detected_category="Dress")
        db.add_all([s_missing, s_traversal])
        db.commit()

        # Deleting non-existent file search returns 204 safely
        res1 = client.delete(f"/api/history/{s_missing.id}", headers=headers)
        assert res1.status_code == 204

        # Deleting traversal path search returns 204 safely and canary remains intact
        res2 = client.delete(f"/api/history/{s_traversal.id}", headers=headers)
        assert res2.status_code == 204
        assert canary_file.exists()
    finally:
        if canary_file.exists():
            canary_file.unlink()
        db.close()


def test_delete_search_endpoint_cascade_and_image_cleanup(client):
    """P4 Test: Verify /api/search/{id} deletion cascades and cleans up unreferenced image."""
    from pathlib import Path
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import Recommendation, SearchHistory, SearchResult
    from app.models.product import Product
    from app.models.user import User

    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    test_filename = "test_search_endpoint_cleanup.jpg"
    test_file_path = upload_dir / test_filename
    test_file_path.write_bytes(b"dummy image for search delete")

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_delete_search@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        prod = Product(name="Search Cascade Prod", category="Shirt", price=600.0)
        db.add(prod)
        db.commit()

        search = SearchHistory(user_id=user.id, image_path=f"uploads/{test_filename}", detected_category="Shirt")
        db.add(search)
        db.commit()

        sr = SearchResult(search_id=search.id, product_id=prod.id, similarity_score=85.0)
        rec = Recommendation(search_id=search.id, product_id=prod.id, mode="best_match", overall_score=85.0)
        db.add_all([sr, rec])
        db.commit()

        search_id = search.id
        res = client.delete(f"/api/search/{search_id}", headers=headers)
        assert res.status_code == 204

        assert db.query(SearchHistory).filter(SearchHistory.id == search_id).first() is None
        assert db.query(SearchResult).filter(SearchResult.search_id == search_id).count() == 0
        assert db.query(Recommendation).filter(Recommendation.search_id == search_id).count() == 0
        assert not test_file_path.exists()
    finally:
        if test_file_path.exists():
            test_file_path.unlink()
        db.close()


def test_delete_history_commit_failure_preserves_image(monkeypatch):
    """P4 Refinement Test: If db.commit fails, image is not unlinked and record is rolled back."""
    from pathlib import Path
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.main import app
    from app.models.activity import SearchHistory
    from app.models.user import User

    client = TestClient(app, raise_server_exceptions=False)
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    test_filename = "test_commit_failure_image.jpg"
    test_file_path = upload_dir / test_filename
    test_file_path.write_bytes(b"image must survive commit failure")

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_commit_fail@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        search = SearchHistory(
            user_id=user.id,
            image_path=f"uploads/{test_filename}",
            detected_category="Shirt",
        )
        db.add(search)
        db.commit()
        search_id = search.id

        # Monkeypatch Session.commit to fail during endpoint execution
        original_commit = Session.commit

        def failing_commit(self):
            raise RuntimeError("Simulated DB commit error")

        monkeypatch.setattr(Session, "commit", failing_commit)

        # Attempt to delete history
        res = client.delete(f"/api/history/{search_id}", headers=headers)
        assert res.status_code == 500
        assert res.json() == {"detail": "Something went wrong. Please try again."}

        # Restore original commit before querying database
        monkeypatch.setattr(Session, "commit", original_commit)

        # Image file MUST still exist on disk
        assert test_file_path.exists()

        # Database record MUST still exist in database due to rollback
        db.rollback()
        persisted = db.query(SearchHistory).filter(SearchHistory.id == search_id).first()
        assert persisted is not None
    finally:
        if test_file_path.exists():
            test_file_path.unlink()
        db.close()


def test_get_search_rehydrates_full_results(client):
    """P5 Test: Verify GET /api/search/{search_id} rehydrates persisted SearchResult & Recommendation."""
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import Recommendation, SearchHistory, SearchResult
    from app.models.product import Product
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(name="Test User", email="test_rehydrate@example.com", password_hash="hash")
            db.add(user)
            db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

        prod = Product(name="Rehydrate Test Shirt", category="Shirt", price=799.0)
        db.add(prod)
        db.commit()

        search = SearchHistory(
            user_id=user.id,
            image_path="uploads/rehydrate_photo.jpg",
            detected_category="Shirt",
            detected_style="Casual",
            detected_color="Blue",
            confidence=95.0,
            result_count=1,
        )
        db.add(search)
        db.commit()

        sr = SearchResult(search_id=search.id, product_id=prod.id, similarity_score=92.0, overall_score=92.0, rank=1)
        rec = Recommendation(
            search_id=search.id,
            product_id=prod.id,
            mode="best_match",
            visual_score=92.0,
            overall_score=92.0,
            reasons='["Exact visual style match", "In budget"]',
        )
        db.add_all([sr, rec])
        db.commit()

        search_id = search.id
        res = client.get(f"/api/search/{search_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # 1. Backwards compatibility check (verify_phase6.py)
        assert data["id"] == search_id
        assert data["detected_category"] == "Shirt"

        # 2. Full rehydration check (ResultsPage.tsx)
        assert data["search_id"] == search_id
        assert len(data["best_matches"]) == 1
        assert data["best_matches"][0]["product"]["id"] == prod.id
        assert data["best_matches"][0]["scores"]["visual_score"] == 92.0
        assert data["best_matches"][0]["scores"]["reasons"] == ["Exact visual style match", "In budget"]
        assert data["best_matches"][0]["store_name"] is not None

        # 3. Item and attribute structures
        assert len(data["detected_items"]) == 1
        assert data["detected_items"][0]["category"] == "Shirt"
        assert len(data["items"]) == 1
        assert data["items"][0]["detected_attributes"]["category"] == "Shirt"
    finally:
        db.close()


def test_get_search_unauthorized_and_ownership(client):
    """P5 Test: Verify GET /api/search/{id} enforces authentication and user ownership."""
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.activity import SearchHistory
    from app.models.user import User

    db = SessionLocal()
    try:
        user1 = db.query(User).filter(User.email == "user1_p5@example.com").first()
        if not user1:
            user1 = User(name="User One", email="user1_p5@example.com", password_hash="hash")
            db.add(user1)
            db.commit()

        user2 = db.query(User).filter(User.email == "user2_p5@example.com").first()
        if not user2:
            user2 = User(name="User Two", email="user2_p5@example.com", password_hash="hash")
            db.add(user2)
            db.commit()

        search1 = SearchHistory(
            user_id=user1.id,
            image_path="uploads/user1_photo.jpg",
            detected_category="Shirt",
        )
        db.add(search1)
        db.commit()

        headers1 = {"Authorization": f"Bearer {create_access_token(str(user1.id))}"}
        headers2 = {"Authorization": f"Bearer {create_access_token(str(user2.id))}"}

        # 1. Unauthenticated request -> 401
        res_unauth = client.get(f"/api/search/{search1.id}")
        assert res_unauth.status_code == 401

        # 2. Owner request -> 200
        res_owner = client.get(f"/api/search/{search1.id}", headers=headers1)
        assert res_owner.status_code == 200

        # 3. Non-owner request -> 404 (ownership check)
        res_non_owner = client.get(f"/api/search/{search1.id}", headers=headers2)
        assert res_non_owner.status_code == 404

        # 4. Non-existent search -> 404
        res_missing = client.get("/api/search/999999", headers=headers1)
        assert res_missing.status_code == 404
    finally:
        db.close()




