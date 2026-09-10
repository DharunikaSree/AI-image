from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

BLOCKED_DOMAINS = {"demo-store.example.com", "example.com", "localhost", "127.0.0.1", "0.0.0.0", "test.com"}


def sanitize_product_url(url: str | None) -> str:
    if not url:
        return ""
    cleaned = str(url).strip()
    if not cleaned:
        return ""
    if not (cleaned.startswith("https://") or cleaned.startswith("http://")):
        return ""
    try:
        parsed = urlparse(cleaned)
        host = (parsed.hostname or "").lower()
        if not host or host in BLOCKED_DOMAINS or "example.com" in host or host == "localhost" or host.endswith(".local") or host.endswith(".example.com"):
            return ""
        return cleaned
    except Exception:
        return ""


class ExternalLinkResponse(BaseModel):
    store_name: str
    url: str
    verification_status: str
    availability_status: str
    destination_type: str = "exact_product"

    @classmethod
    def from_orm_link(cls, link: Any) -> Optional["ExternalLinkResponse"]:
        if not link:
            return None
        raw_url = getattr(link, "external_url", None) or (link.get("external_url") if isinstance(link, dict) else "")
        cleaned_url = sanitize_product_url(raw_url)
        if not cleaned_url:
            return None
        store = getattr(link, "store_name", None) or (link.get("store_name") if isinstance(link, dict) else "Store")
        v_status = getattr(link, "verification_status", None) or (link.get("verification_status") if isinstance(link, dict) else "unverified")
        a_status = getattr(link, "availability_status", None) or (link.get("availability_status") if isinstance(link, dict) else "available")
        d_type = getattr(link, "destination_type", None) or (link.get("destination_type") if isinstance(link, dict) else None)
        if not d_type:
            if str(v_status).lower() == "verified":
                d_type = "exact_product"
            elif str(v_status).lower() == "official_store":
                d_type = "official_store"
            elif str(v_status).lower() == "search_destination":
                d_type = "shopping_search"
            else:
                d_type = "exact_product"

        if a_status in ("in_stock", "available", "true", "True"):
            a_status = "available"
        elif a_status in ("out_of_stock", "unavailable", "false", "False"):
            a_status = "unavailable"

        return cls(
            store_name=store,
            url=cleaned_url,
            verification_status=v_status,
            availability_status=a_status,
            destination_type=d_type,
        )

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    brand: str
    category: str
    subcategory: str
    style: str
    color: str
    pattern: str
    price: float
    discount_price: float | None
    currency: str
    image_url: str
    product_url: str
    platform: str
    availability: bool
    group_key: str
    external_links: list[ExternalLinkResponse] = []

    @field_validator("product_url", mode="before")
    @classmethod
    def validate_url(cls, v: str | None) -> str:
        return sanitize_product_url(v)

    @field_validator("external_links", mode="before")
    @classmethod
    def validate_external_links(cls, v: Any) -> list[ExternalLinkResponse]:
        if not v:
            return []
        cleaned_links = []
        for item in v:
            parsed = ExternalLinkResponse.from_orm_link(item)
            if parsed:
                cleaned_links.append(parsed)
        return cleaned_links

    class Config:
        from_attributes = True



class ProductCreate(BaseModel):
    name: str
    description: str = ""
    brand: str = ""
    category: str
    subcategory: str = ""
    style: str = ""
    color: str = ""
    pattern: str = "Solid"
    price: float = 0
    discount_price: float | None = None
    currency: str = "INR"
    image_url: str = ""
    product_url: str = ""
    platform: str = "DeepFashion"
    availability: bool = True
    group_key: str = ""

    @field_validator("product_url", mode="before")
    @classmethod
    def validate_url(cls, v: str | None) -> str:
        return sanitize_product_url(v)


class ProductUpdate(ProductCreate):
    pass


class PaginatedProductResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    limit: int
    total_pages: int
