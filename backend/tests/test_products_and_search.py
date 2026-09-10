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

