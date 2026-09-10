# Phase 8 — Step 2: Architecture Design for Real E-Commerce Product Linking

**Project:** Lumière AI Fashion Search  
**Document:** System Architecture & Data Design  
**Date:** August 2026  
**Status:** Approved for Implementation (Design Only — No Code Modified Yet)

---

## 1. Core Principles & Design Constraints

To ensure production integrity, zero-hallucination compliance, and high user trust, this architecture adheres to strict engineering rules:

1. **Zero URL Hallucination:** The system will never fabricate, guess, or synthesize placeholder URLs (e.g., no `demo-store.example.com` or guessed numeric product IDs).
2. **Explicit Verification Before Display:** A product is never presented as "Available on [Store]" unless a genuine, verified e-commerce URL has been acquired, validated, and stored in the database.
3. **Pipeline Preservation:** The existing visual intelligence stack (ViT classification, multi-attribute classification, CLIP embeddings, FAISS vector index, multi-factor recommendation scoring) remains 100% intact. Product links are enriched at the retrieval/presentation layer.
4. **Graceful Fallback:** Catalog items without a verified link explicitly and transparently display **"Store Link Unavailable"** with clear messaging that the item is part of the research catalog.
5. **Secure Outbound Handling:** All external links enforce protocol validation, strict host whitelisting, HTTPS enforcement, and secure frontend attributes (`rel="noopener noreferrer"`, `target="_blank"`).

---

## 2. End-to-End Architecture Flow

```
┌────────────────────────────────────────────────────────┐
│             DeepFashion Catalog (~44,441 Items)         │
│  (Brand, Name, Category, Color, Style, Gender, Image)  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             AI Recommendation Engine                   │
│   • ViT & Attribute Classification                     │
│   • 512-d CLIP Embedding Generation                    │
│   • Sub-Millisecond FAISS Index Retrieval              │
│   • Multi-Attribute & Preference Scoring               │
└──────────────────────────┬─────────────────────────────┘
                           │ Candidate Products
                           ▼
┌────────────────────────────────────────────────────────┐
│             Product Metadata Layer                     │
│   (Retrieves Product Entity + Associated ProductLinks) │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             Product-Link Mapping Service               │
│   • Checks ProductLink verification_status             │
│   • Selects Primary Active Verified Link               │
│   • Evaluates availability_status                      │
└──────────────────────────┬─────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   [Verified Link Present]    [No Verified Link]
              │                         │
              ▼                         ▼
  Product Details API:       Product Details API:
  `product_url`: real URL    `product_url`: ""
  `verification_status`:     `verification_status`:
    "verified"                 "unavailable"
              │                         │
              ▼                         ▼
  Frontend (ProductDetailPage): Frontend (ProductDetailPage):
  [ Visit Store ↗ (Active) ]   [ Store Link Unavailable (Disabled) ]
```

---

## 3. Data Model Design (`ProductLink`)

### 3.1 SQLAlchemy Database Model (`backend/app/models/product.py`)

A dedicated `ProductLink` table provides 1-to-many link management per product (enabling multi-store availability, price comparison, or brand official links while maintaining clean separation from core product metadata).

```python
class VerificationStatus(str, Enum):
    VERIFIED = "verified"          # URL verified live, HTTP 200, valid product landing page
    UNVERIFIED = "unverified"      # Ingested from feed/admin, pending live verification
    UNAVAILABLE = "unavailable"    # Item confirmed out-of-stock / discontinued on merchant site
    INVALID = "invalid"            # Broken link, 404, DNS failure, or blocked domain

class AvailabilityStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    UNKNOWN = "unknown"

class ProductLink(Base):
    __tablename__ = "product_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(80), nullable=False)  # e.g., "Myntra", "Amazon", "Official Brand Store"
    external_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified", index=True)
    availability_status: Mapped[str] = mapped_column(String(30), default="unknown")
    price_on_store: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to parent Product
    product: Mapped["Product"] = relationship(back_populates="links")
```

### 3.2 Pydantic Schemas (`backend/app/schemas/product.py`)

```python
class ProductLinkResponse(BaseModel):
    id: int
    product_id: int
    source: str
    external_url: str
    verification_status: str
    availability_status: str
    price_on_store: float | None = None
    currency: str = "INR"
    is_primary: bool = False
    last_verified_at: datetime | None = None

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
    product_url: str                  # Resolves to primary verified URL or ""
    platform: str                     # Primary source name (e.g. "Myntra", "Official Brand Store", "DeepFashion")
    verification_status: str          # "verified" | "unavailable" | "unverified" | "invalid"
    availability: bool
    group_key: str
    links: list[ProductLinkResponse] = []  # Detailed multi-store links

    class Config:
        from_attributes = True
```

---

## 4. Verification & Status State Machine

```
               ┌───────────────────────┐
               │    New Link Ingested  │
               └───────────┬───────────┘
                           │ (Initial state)
                           ▼
               ┌───────────────────────┐
               │      UNVERIFIED       │
               └───────────┬───────────┘
                           │
                 [Verification Worker]
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
HTTP 200 & In Stock   HTTP 200 & Sold Out    HTTP 404 / Error /
Domain Whitelisted    Merchant Inactive      Invalid Scheme
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   VERIFIED   │    │ UNAVAILABLE  │    │   INVALID    │
│  (in_stock)  │    │(out_of_stock)│    │(Never Shown) │
└──────┬───────┘    └──────────────┘    └──────────────┘
       │
 [Periodic Re-check / 7 Days]
       │
       └───> Re-evaluates status
```

### Status Definitions:
1. **`verified`**: The URL is syntactically valid, matches the merchant domain whitelist, responded with HTTP 200, and is confirmed active. **Only `verified` links are clickable in the UI.**
2. **`unverified`**: Newly added link awaiting asynchronous or automated verification.
3. **`unavailable`**: Previously valid link where the merchant has marked the item as out-of-stock or discontinued. UI renders "Currently Unavailable on [Store]".
4. **`invalid`**: Broken link (404/500), blocked host, redirect loop, or malformed URL. Excluded from consumer responses.

---

## 5. Supported E-Commerce Sources & Whitelist Architecture

To prevent phishing, malformed links, or affiliate injection attacks, all outbound e-commerce links are validated against an authoritative merchant registry:

| Source Identifier | Display Name | Canonical Domain Whitelist | Search Query Template Support |
| :--- | :--- | :--- | :--- |
| `Myntra` | Myntra | `myntra.com`, `www.myntra.com` | `https://www.myntra.com/{query}` |
| `Amazon` | Amazon Fashion | `amazon.in`, `www.amazon.in` | `https://www.amazon.in/s?k={query}` |
| `Flipkart` | Flipkart | `flipkart.com`, `www.flipkart.com` | `https://www.flipkart.com/search?q={query}` |
| `Ajio` | Ajio | `ajio.com`, `www.ajio.com` | `https://www.ajio.com/search/?text={query}` |
| `Tata CLiQ` | Tata CLiQ | `tatacliq.com`, `www.tatacliq.com` | `https://www.tatacliq.com/search/?searchCategory=all&text={query}` |
| `Official Brand Store` | Official Brand Store | Whitelisted brand domains (e.g., `nike.com`, `adidas.co.in`, `puma.com`, `levi.in`, `fabindia.com`, `casioindiashop.com`, `titan.co.in`) | Direct brand search endpoint |
| `Other Verified Retailer` | Verified Retailer | Explicit admin-whitelisted retailer domain | Verified SKU page |

---

## 6. Integration with AI Recommendation Pipeline

The recommendation pipeline remains strictly modular and decoupled from link availability:

1. **Visual Search & Scoring (Zero Changes to AI Core):**
   - Garment crop image is analyzed by `ViT` & multi-attribute classifier (`app/services/ai_classifier.py`).
   - Query embedding (512-d) generated by `CLIP` (`app/services/embedding.py`).
   - Nearest neighbors retrieved via `FAISS` in `< 1ms`.
   - Products scored across visual similarity, category, color, style, pattern, and user preferences (`app/services/recommendation.py`).

2. **Link Resolution at Serialization:**
   - When constructing `ProductResponse`, the application inspects `product.links`:
     - If one or more `verified` links exist, the primary verified link is assigned to `ProductResponse.product_url`, and the source is assigned to `ProductResponse.platform`.
     - If no verified link exists, `product_url` is set to `""`, and `ProductResponse.verification_status` is set to `"unavailable"`.

3. **No Ranking Bias by Link Status:**
   - Visual recommendation relevance is never penalized or altered if an item lacks an external store link. Visual similarity and garment attributes remain the single source of truth for match scores.

---

## 7. Frontend User Experience Design

### 7.1 Product Details Page (`ProductDetailPage.tsx`)

#### State A: Verified Real Store Link Available
```
┌─────────────────────────────────────────────────────────────┐
│ [Product Photo]   Classic Men Navy Blue Shirt               │
│                   Brand: Turtle • INR 1,799                 │
│                                                             │
│                   [ Garment Attributes Box ]                │
│                                                             │
│                   [ Save to Favorites ]                     │
│                   [ Visit Store on Myntra ↗ ] (Primary CTA) │
│                                                             │
│                   ✓ Verified link on Myntra Official        │
└─────────────────────────────────────────────────────────────┘
```

#### State B: No Verified Link (Standard DeepFashion Item)
```
┌─────────────────────────────────────────────────────────────┐
│ [Product Photo]   Vintage Denim Jacket                      │
│                   Brand: DenimLab • INR 1,999               │
│                                                             │
│                   [ Garment Attributes Box ]                │
│                                                             │
│                   [ Save to Favorites ]                     │
│                   [ Store Link Unavailable ] (Disabled CTA) │
│                                                             │
│                   ℹ This item is part of the research       │
│                     catalog. Live checkout unavailable.     │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Security Headers & Attributes
All outbound links in React are rendered strictly as:
```tsx
<a
  href={product.product_url}
  target="_blank"
  rel="noopener noreferrer"
  className="btn-primary flex items-center justify-center gap-2"
>
  Visit Store on {product.platform} <ExternalLink size={15} />
</a>
```

---

## 8. Admin Management & Link Operations

To support administrative oversight, the Admin Dashboard will provide:
1. **Link Management Modal:** View, add, update, and remove merchant links for any product.
2. **One-Click Link Verification:** Admin trigger to test external URL reachability and validate against merchant whitelist.
3. **Batch Ingestion Tool:** Ingest verified merchant feed CSV/JSON files matching product metadata without manual single-entry.

---

## 9. Security, Validation & Reliability Controls

1. **Protocol Restriction:** Only `https://` (and strictly whitelisted `http://` for local test harnesses) allowed. All `javascript:`, `data:`, `file:`, or relative URIs are stripped.
2. **SSRF Prevention:** Backend verifier prevents internal network scanning (rejects `127.0.0.1`, `localhost`, `169.254.169.254`, `10.0.0.0/8`, `192.168.0.0/16`).
3. **Timeout Controls:** Automated verifier uses strict 5-second timeouts with exponential backoff and rate limiting to avoid overloading external merchant servers.
4. **Anti-Phishing Verification:** Hostnames must strictly match exact domains or designated subdomains of authorized merchants.

---

## 10. Summary of Architectural Integrity

| Requirement | Architectural Guarantee |
| :--- | :--- |
| **No Fake URLs** | Only verified URLs with HTTP 200 from whitelisted merchant domains are set to `verified`. |
| **No Demo Placeholders** | `demo-store.example.com` and `example.com` remain globally blacklisted in both backend and frontend. |
| **No Guessed SKU IDs** | URLs are only created through verified merchant partner feeds, brand mappings, or verified admin curation. |
| **Truth in Availability** | If no verified link exists, the UI clearly displays "Store Link Unavailable". |
| **AI Stack Preservation** | ViT, CLIP, FAISS, and scoring functions remain untouched and isolated from external URL state. |
