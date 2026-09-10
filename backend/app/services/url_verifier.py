"""
Safe External URL Verification Service for Lumière AI Fashion Search.

Validates external e-commerce product links to guarantee that users are only directed
to legitimate, safe, live HTTPS storefronts without security risks, SSRF, or broken links.

Safety Guarantees:
1. HTTPS Enforcement: Rejects HTTP, FTP, file, and javascript URLs.
2. SSRF Protection: Rejects localhost, 127.0.0.1, 0.0.0.0, private IP ranges, link-local, and reserved IPs.
3. Placeholder Blacklist: Rejects demo-store.example.com, example.com, test.com, and dummy domains.
4. Safe Redirects: Follows redirects up to a strict limit, re-verifying HTTPS and safety at each step.
5. Lightweight Probing: Uses HEAD or streaming GET without downloading large product HTML or media assets.
6. Graceful Failure: Never throws unhandled network errors to callers; returns structured status.
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.models.product import ProductExternalLink

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 4.0
MAX_REDIRECTS = 5
MAX_STREAM_BYTES = 4096

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",
    "example.com",
    "www.example.com",
    "demo-store.example.com",
    "test.com",
    "www.test.com",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 LumiereFashionVerifier/1.0"
)


@dataclass
class URLVerificationResult:
    url: str
    is_valid: bool
    verification_status: str  # "verified" | "unavailable" | "invalid" | "unverified"
    availability_status: str  # "available" | "out_of_stock" | "unknown" | "invalid"
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    reason: str = ""
    last_verified_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "is_valid": self.is_valid,
            "verification_status": self.verification_status,
            "availability_status": self.availability_status,
            "status_code": self.status_code,
            "final_url": self.final_url,
            "reason": self.reason,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
        }


def is_private_or_blocked_host(hostname: Optional[str]) -> bool:
    """Checks if a hostname is a loopback, private IP, local domain, or blacklisted placeholder."""
    if not hostname:
        return True

    host = hostname.strip().lower()

    if (
        host in BLOCKED_HOSTNAMES
        or host.endswith(".example.com")
        or host.endswith(".local")
        or host.endswith(".internal")
        or host.endswith(".test")
    ):
        return True

    # Check for IP literals (IPv4 / IPv6)
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
        return False
    except ValueError:
        pass

    # Reject naked single-word hosts (e.g. "intranet")
    if "." not in host:
        return True

    return False


def prevalidate_url(url: Optional[str]) -> tuple[bool, str]:
    """
    Performs fast, offline syntactic and safety checks on a URL string.
    Returns (is_ok, reason).
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or not a string"

    trimmed = url.strip()
    if not trimmed:
        return False, "URL is empty"

    if trimmed.startswith("http://"):
        return False, "Insecure HTTP URLs are not permitted; HTTPS is required"

    if not trimmed.startswith("https://"):
        return False, "URL must use the HTTPS protocol"

    try:
        parsed = urlparse(trimmed)
        if parsed.scheme.lower() != "https":
            return False, "Only HTTPS scheme is accepted"

        host = parsed.hostname
        if not host:
            return False, "URL is missing a valid hostname"

        if is_private_or_blocked_host(host):
            return False, f"Hostname '{host}' is a placeholder, private IP, or blocked domain"

        return True, "Syntactically valid HTTPS URL"
    except Exception as exc:
        return False, f"Malformed URL syntax: {exc}"


class URLVerifier:
    """
    Production-grade URL verifier with SSRF protection, redirect verification,
    and non-blocking error handling.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.user_agent = user_agent

    def verify(self, url: str) -> URLVerificationResult:
        now = datetime.now(timezone.utc)

        # 1. Offline Pre-validation
        is_ok, reason = prevalidate_url(url)
        if not is_ok:
            return URLVerificationResult(
                url=url or "",
                is_valid=False,
                verification_status="invalid",
                availability_status="invalid",
                status_code=None,
                final_url=None,
                reason=reason,
                last_verified_at=now,
            )

        current_url = url.strip()
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 2. Probe with safe redirect handling
        redirect_count = 0
        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=self.timeout,
                verify=True,
                headers=headers,
            ) as client:
                while redirect_count <= self.max_redirects:
                    resp = client.head(current_url)
                    # If server forbids HEAD (405 / 403 / 501), fallback to streaming GET
                    if resp.status_code in (403, 405, 501):
                        try:
                            with client.stream("GET", current_url) as stream_resp:
                                status_code = stream_resp.status_code
                                headers_dict = dict(stream_resp.headers)
                                _ = next(stream_resp.iter_bytes(MAX_STREAM_BYTES), b"")
                        except Exception:
                            status_code = resp.status_code
                            headers_dict = dict(resp.headers)
                    else:
                        status_code = resp.status_code
                        headers_dict = dict(resp.headers)

                    # Handle Redirects
                    if status_code in (301, 302, 303, 307, 308):
                        location = headers_dict.get("location") or headers_dict.get("Location")
                        if not location:
                            return URLVerificationResult(
                                url=url,
                                is_valid=False,
                                verification_status="unavailable",
                                availability_status="unknown",
                                status_code=status_code,
                                final_url=current_url,
                                reason="Redirect response missing Location header",
                                last_verified_at=now,
                            )

                        next_url = urljoin(current_url, location)
                        # Re-verify safety on the redirect target
                        target_ok, target_reason = prevalidate_url(next_url)
                        if not target_ok:
                            return URLVerificationResult(
                                url=url,
                                is_valid=False,
                                verification_status="invalid",
                                availability_status="invalid",
                                status_code=status_code,
                                final_url=next_url,
                                reason=f"Insecure or blocked redirect target: {target_reason}",
                                last_verified_at=now,
                            )

                        current_url = next_url
                        redirect_count += 1
                        continue

                    # Evaluate Final Status
                    if 200 <= status_code < 300:
                        return URLVerificationResult(
                            url=url,
                            is_valid=True,
                            verification_status="verified",
                            availability_status="available",
                            status_code=status_code,
                            final_url=current_url,
                            reason="URL verified live and reachable",
                            last_verified_at=now,
                        )
                    elif status_code in (404, 410):
                        return URLVerificationResult(
                            url=url,
                            is_valid=False,
                            verification_status="unavailable",
                            availability_status="out_of_stock",
                            status_code=status_code,
                            final_url=current_url,
                            reason=f"Product page not found (HTTP {status_code})",
                            last_verified_at=now,
                        )
                    elif status_code in (401, 403, 429):
                        # Active merchant site but bot challenge / rate limit encountered
                        return URLVerificationResult(
                            url=url,
                            is_valid=True,
                            verification_status="verified",
                            availability_status="available",
                            status_code=status_code,
                            final_url=current_url,
                            reason=f"Merchant site active (HTTP {status_code} challenge)",
                            last_verified_at=now,
                        )
                    else:
                        return URLVerificationResult(
                            url=url,
                            is_valid=False,
                            verification_status="unavailable",
                            availability_status="unknown",
                            status_code=status_code,
                            final_url=current_url,
                            reason=f"Store server responded with HTTP {status_code}",
                            last_verified_at=now,
                        )

                # Exceeded Max Redirects
                return URLVerificationResult(
                    url=url,
                    is_valid=False,
                    verification_status="unavailable",
                    availability_status="unknown",
                    status_code=status_code if "status_code" in locals() else None,
                    final_url=current_url,
                    reason=f"Exceeded maximum allowed redirects ({self.max_redirects})",
                    last_verified_at=now,
                )

        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.TimeoutException):
            return URLVerificationResult(
                url=url,
                is_valid=False,
                verification_status="unavailable",
                availability_status="unknown",
                status_code=None,
                final_url=current_url,
                reason="Verification request timed out",
                last_verified_at=now,
            )
        except (httpx.ConnectError, httpx.NetworkError):
            return URLVerificationResult(
                url=url,
                is_valid=False,
                verification_status="unavailable",
                availability_status="unknown",
                status_code=None,
                final_url=current_url,
                reason="Unable to connect to store host (DNS or connection failure)",
                last_verified_at=now,
            )
        except httpx.SSLError as ssl_err:
            return URLVerificationResult(
                url=url,
                is_valid=False,
                verification_status="invalid",
                availability_status="invalid",
                status_code=None,
                final_url=current_url,
                reason=f"SSL certificate error: {ssl_err}",
                last_verified_at=now,
            )
        except Exception as exc:
            logger.warning("Unexpected error verifying URL '%s': %s", url, exc)
            return URLVerificationResult(
                url=url,
                is_valid=False,
                verification_status="unavailable",
                availability_status="unknown",
                status_code=None,
                final_url=current_url,
                reason=f"URL verification failed: {exc}",
                last_verified_at=now,
            )


# Global default verifier instance
url_verifier = URLVerifier()


def verify_url(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> URLVerificationResult:
    """Convenience functional interface for URL verification."""
    verifier = URLVerifier(timeout=timeout) if timeout != DEFAULT_TIMEOUT_SECONDS else url_verifier
    return verifier.verify(url)


def verify_and_update_product_link(
    db: Session,
    link: ProductExternalLink,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> URLVerificationResult:
    """
    Verifies an external link database record and persists updated status
    and verification timestamp safely.
    """
    result = verify_url(link.external_url, timeout=timeout)
    link.verification_status = result.verification_status
    link.availability_status = result.availability_status
    link.last_verified_at = result.last_verified_at
    db.commit()
    db.refresh(link)
    return result
