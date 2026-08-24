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
    assert body["ai_mode"] == "demo"
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
