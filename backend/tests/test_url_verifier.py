"""
Unit tests for Safe URL Verification Service (Phase 8 Step 9)
"""
from datetime import datetime
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.models.product import Product, ProductExternalLink
from app.services.url_verifier import (
    URLVerifier,
    URLVerificationResult,
    is_private_or_blocked_host,
    prevalidate_url,
    verify_url,
    verify_and_update_product_link,
)


def test_is_private_or_blocked_host():
    # Blocked placeholders
    assert is_private_or_blocked_host("example.com") is True
    assert is_private_or_blocked_host("www.example.com") is True
    assert is_private_or_blocked_host("demo-store.example.com") is True
    assert is_private_or_blocked_host("sub.demo-store.example.com") is True
    assert is_private_or_blocked_host("test.com") is True
    assert is_private_or_blocked_host("dev.test") is True

    # Local / Private / Loopback IPs
    assert is_private_or_blocked_host("localhost") is True
    assert is_private_or_blocked_host("127.0.0.1") is True
    assert is_private_or_blocked_host("0.0.0.0") is True
    assert is_private_or_blocked_host("192.168.1.1") is True
    assert is_private_or_blocked_host("10.0.0.1") is True
    assert is_private_or_blocked_host("172.16.0.5") is True
    assert is_private_or_blocked_host("169.254.169.254") is True
    assert is_private_or_blocked_host("my-internal-server") is True

    # Legitimate public hostnames
    assert is_private_or_blocked_host("www.myntra.com") is False
    assert is_private_or_blocked_host("amazon.in") is False
    assert is_private_or_blocked_host("in.puma.com") is False
    assert is_private_or_blocked_host("assets.myntassets.com") is False


def test_prevalidate_url_rejections():
    # Empty & malformed
    assert prevalidate_url("")[0] is False
    assert prevalidate_url(None)[0] is False
    assert prevalidate_url("not a url")[0] is False
    assert prevalidate_url("javascript:alert(1)")[0] is False

    # HTTP rejection
    is_ok, reason = prevalidate_url("http://www.myntra.com/product/123")
    assert is_ok is False
    assert "HTTPS is required" in reason

    # Placeholder & Private rejection
    assert prevalidate_url("https://example.com/item")[0] is False
    assert prevalidate_url("https://demo-store.example.com/p/1")[0] is False
    assert prevalidate_url("https://localhost:8000/api")[0] is False
    assert prevalidate_url("https://127.0.0.1:5000/product")[0] is False
    assert prevalidate_url("https://0.0.0.0/test")[0] is False

    # Valid HTTPS URL
    is_ok, reason = prevalidate_url("https://www.myntra.com/shirts/15970")
    assert is_ok is True


@patch("httpx.Client.head")
def test_verify_valid_https_url(mock_head):
    # Mock HTTP 200 on HEAD
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_head.return_value = mock_resp

    url = "https://www.myntra.com/shirts/turtle/15970/buy"
    res = verify_url(url)

    assert isinstance(res, URLVerificationResult)
    assert res.is_valid is True
    assert res.verification_status == "verified"
    assert res.availability_status == "available"
    assert res.status_code == 200
    assert res.final_url == url
    assert res.last_verified_at is not None


def test_verify_http_url_rejected():
    url = "http://www.amazon.in/dp/B08XYZ1234"
    res = verify_url(url)

    assert res.is_valid is False
    assert res.verification_status == "invalid"
    assert res.availability_status == "invalid"
    assert "HTTPS is required" in res.reason


def test_verify_placeholder_url_rejected():
    url = "https://demo-store.example.com/product/30805"
    res = verify_url(url)

    assert res.is_valid is False
    assert res.verification_status == "invalid"
    assert "blocked domain" in res.reason


def test_verify_invalid_malformed_url():
    res = verify_url("https://")
    assert res.is_valid is False
    assert res.verification_status == "invalid"


@patch("httpx.Client.head")
def test_verify_unreachable_url_404(mock_head):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {}
    mock_head.return_value = mock_resp

    url = "https://www.myntra.com/non-existent-product-999999"
    res = verify_url(url)

    assert res.is_valid is False
    assert res.verification_status == "unavailable"
    assert res.availability_status == "out_of_stock"
    assert res.status_code == 404


@patch("httpx.Client.head")
def test_verify_unreachable_network_error(mock_head):
    # Simulate network or DNS connection error
    mock_head.side_effect = httpx.ConnectError("DNS resolution failed for store")

    url = "https://www.unreachable-fake-fashion-store-domain.com/item/1"
    res = verify_url(url)

    assert res.is_valid is False
    assert res.verification_status == "unavailable"
    assert res.availability_status == "unknown"
    assert "Unable to connect" in res.reason or "unreachable" in res.reason.lower()


@patch("httpx.Client.head")
def test_verify_timeout_handling(mock_head):
    # Simulate request timeout
    mock_head.side_effect = httpx.ReadTimeout("Server took too long to respond")

    url = "https://www.slow-retailer-server.com/product/123"
    res = verify_url(url)

    assert res.is_valid is False
    assert res.verification_status == "unavailable"
    assert res.availability_status == "unknown"
    assert "timed out" in res.reason.lower()


@patch("httpx.Client.head")
def test_verify_safe_redirect(mock_head):
    # Step 1: 301 Redirect to https://www.myntra.com/product/final
    resp_redirect = MagicMock()
    resp_redirect.status_code = 301
    resp_redirect.headers = {"Location": "https://www.myntra.com/product/final"}

    # Step 2: 200 OK at final target
    resp_final = MagicMock()
    resp_final.status_code = 200
    resp_final.headers = {"content-type": "text/html"}

    mock_head.side_effect = [resp_redirect, resp_final]

    res = verify_url("https://www.myntra.com/product/shortlink")

    assert res.is_valid is True
    assert res.verification_status == "verified"
    assert res.status_code == 200
    assert res.final_url == "https://www.myntra.com/product/final"


@patch("httpx.Client.head")
def test_verify_unsafe_redirect_blocked(mock_head):
    # Attempt redirect to an insecure internal IP
    resp_redirect = MagicMock()
    resp_redirect.status_code = 302
    resp_redirect.headers = {"Location": "http://127.0.0.1:8000/internal"}

    mock_head.return_value = resp_redirect

    res = verify_url("https://www.myntra.com/redirect-trap")

    assert res.is_valid is False
    assert res.verification_status == "invalid"
    assert "Insecure or blocked redirect target" in res.reason


def test_verify_and_update_product_link_model():
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # Create product and external link in test DB
        product = Product(
            name="Turtle Blue Casual Shirt",
            category="Shirt",
            brand="Turtle",
            price=1499.0,
        )
        db.add(product)
        db.commit()

        link = ProductExternalLink(
            product_id=product.id,
            store_name="Myntra",
            external_url="https://www.myntra.com/shirts/turtle/15970",
            verification_status="unverified",
            availability_status="unknown",
        )
        db.add(link)
        db.commit()

        with patch("httpx.Client.head") as mock_head:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {}
            mock_head.return_value = mock_resp

            result = verify_and_update_product_link(db, link)

            assert result.verification_status == "verified"
            assert link.verification_status == "verified"
            assert link.availability_status == "available"
            assert link.last_verified_at is not None
    finally:
        db.close()
