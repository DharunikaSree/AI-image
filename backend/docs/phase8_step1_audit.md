# Phase 8 — Step 1: Audit of Current Product URL System

**Project:** Lumière AI Fashion Search  
**Audit Date:** August 2026  
**Scope:** Complete end-to-end audit of product URL data generation, storage, serialization, validation, display, and dataset metadata.

---

## 1. Executive Summary

This audit examines the existing product URL system across the backend (FastAPI, SQLAlchemy, SQLite, FAISS, CLIP/ViT) and frontend (React, Vite, TypeScript). Currently, all ~44,441 products in the DeepFashion catalog display **"Store Link Unavailable"** on the Product Details page. 

The audit reveals that:
1. **The underlying dataset** (Kaggle Fashion Product Images / Myntra archive) never contained store or checkout URLs.
2. **Earlier placeholders** (e.g., `https://demo-store.example.com/...`) were intentionally scrubbed by data-cleansing scripts and are actively blocked by both backend and frontend sanitizers.
3. **The product link architecture** (database column, Pydantic schemas, API responses, and frontend validation/rendering) is fully implemented, secure, and ready to accept genuine external URLs or dynamic search/affiliate mappings.
4. **Rich metadata exists** for all 44,441 items (Brand, Name, Category, Article Type, Gender, Color, Style, Price), enabling deterministic external store resolution.

---

## 2. Current Architecture & Component Inspection

### 2.1 Product Database Schema (`backend/app/models/product.py`)
- **Table Name:** `products` (SQLite database: `backend/fashion.db`)
- **SQLAlchemy Model:** `Product`
- **URL-related columns:**
  ```python
  product_url: Mapped[str] = mapped_column(String(500), default="")
  platform: Mapped[str] = mapped_column(String(120), default="Demo Store")
  image_url: Mapped[str] = mapped_column(String(500), default="")
  ```
- **Full Schema Fields:** `id` (int, PK), `name` (str), `description` (text), `brand` (str), `category` (str, indexed), `subcategory` (str), `style` (str), `color` (str), `pattern` (str), `price` (float), `discount_price` (float|None), `currency` (str), `image_url` (str), `product_url` (str), `platform` (str), `availability` (bool), `embedding_reference` (text), `group_key` (str), `created_at` (datetime), `updated_at` (datetime).

### 2.2 Product Pydantic Schemas (`backend/app/schemas/product.py` & `search.py`)
- **`ProductResponse`:** Serializes product records for all consumer-facing endpoints. Contains `product_url: str`.
- **`ProductCreate` / `ProductUpdate`:** Used by Admin endpoints.
- **Backend Sanitizer (`sanitize_product_url`):**
  ```python
  BLOCKED_DOMAINS = {"demo-store.example.com", "example.com", "localhost", "127.0.0.1", "0.0.0.0", "test.com"}

  def sanitize_product_url(url: str | None) -> str:
      if not url:
          return ""
      cleaned = str(url).strip()
      if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
          return ""
      try:
          parsed = urlparse(cleaned)
          host = (parsed.hostname or "").lower()
          if not host or host in BLOCKED_DOMAINS or "example.com" in host or host == "localhost" or host.endswith(".local"):
              return ""
          return cleaned
      except Exception:
          return ""
  ```
  `@field_validator("product_url", mode="before")` strictly cleanses input, returning empty string `""` for missing or blocked domains.

### 2.3 Import & Seed Scripts (`scripts/`)
1. **`scripts/import_deepfashion_to_db.py`:**
   - Ingests 44,441 records from `data/deepfashion_metadata.json` into `backend/fashion.db`.
   - Explicitly sets `product_url=""` and `platform="DeepFashion"`.
2. **`scripts/preprocess_deepfashion.py`:**
   - Preprocesses raw Kaggle dataset (`styles.csv` + `images/`).
   - Fields parsed: `id`, `gender`, `masterCategory`, `subCategory`, `articleType`, `baseColour`, `season`, `year`, `usage`, `productDisplayName`.
   - Output files: `data/deepfashion_metadata.json`, `data/deepfashion_catalog.csv`, `data/deepfashion_summary.json`.
   - **No URL column** is present in `styles.csv`.
3. **`scripts/clean_placeholder_urls.py`:**
   - Scrubbed legacy placeholder URLs (`%demo-store%`, `%example.com%`, `%localhost%`, `%127.0.0.1%`) from all records.
4. **`scripts/seed_database.py`:**
   - Demo catalog seeder; sets `product_url=""`.

### 2.4 Product API Endpoints
All endpoints returning product representations utilize `ProductResponse`:
- `GET /api/products`: Paginated catalog with category/style/color filters.
- `GET /api/products/{product_id}`: Single product detail retrieval.
- `GET /api/products/{product_id}/variants`: Color variants sharing `group_key`.
- `POST /api/search/image`: Single garment image search with ViT/CLIP/FAISS.
- `POST /api/search/multi-item`: Multi-garment Shop The Look search.
- `GET /api/recommendations/{search_id}`: Ranked recommendation lists (`best_match`, `best_value`, `similar_style`, `lowest_price`, `premium`).
- `GET /api/admin/products`, `POST /api/admin/products`, `PUT /api/admin/products/{id}`: Admin product management.

### 2.5 Frontend Components & Pages (`frontend/src/`)
1. **`frontend/src/utils/url.ts` (`isGenuineExternalUrl`):**
   - Validates URLs against protocol whitelist (`http://`, `https://`) and hostname blacklist (`BLOCKED_HOSTNAMES`, `*.example.com`, `*.local`, `localhost`, IP addresses).
2. **`frontend/src/components/ProductCard.tsx`:**
   - Used in Catalog, Search Results, Multi-Item Shop The Look, and Product Detail variants.
   - Shows image, brand, title, price, discount, and a `"View Details"` button navigating internally to `/products/${product.id}`.
   - Does not render external links directly (delegated to Product Detail page).
3. **`frontend/src/pages/ProductDetailPage.tsx`:**
   - Checks `const hasRealStoreUrl = isGenuineExternalUrl(product.product_url);`.
   - If `true`: Renders active `"Visit Store"` anchor tag (`target="_blank"`, `rel="noopener noreferrer"`).
   - If `false`: Renders disabled `"Store Link Unavailable"` button with explanatory text (*"This item is part of the DeepFashion research catalog. Live ecommerce checkout is not available for this item."*).
4. **`frontend/src/pages/SearchPage.tsx` & `ResultsPage.tsx`:**
   - Orchestrates multi-item garment cropping, upload, and presentation.
   - Each recommendation card links to `/products/:id` where the store action is surfaced.
5. **`frontend/src/pages/AdminDashboardPage.tsx`:**
   - Allows administrators to view, create, and edit `product_url` manually for any catalog item.

---

## 3. Current Data Flow

```
[Raw Kaggle styles.csv + images]
            │
            ▼
[preprocess_deepfashion.py] ──> Extracts attributes (No URLs in source dataset)
            │
            ▼
[data/deepfashion_metadata.json] ──> 44,441 records with brand, name, category, price
            │
            ▼
[import_deepfashion_to_db.py] ──> Sets product_url="" in SQLite fashion.db
            │
            ▼
[FastAPI Endpoints] ──> Sanitizes & serializes ProductResponse (product_url="")
            │
            ▼
[Frontend UI] ──> isGenuineExternalUrl("") returns false
            │
            ▼
[ProductDetailPage.tsx] ──> Renders "Store Link Unavailable" (disabled button)
```

---

## 4. Detailed Findings & Root Cause

### 4.1 Root Cause of "Store Link Unavailable"
1. **Dataset Origin:** The 44,441 products originate from the Kaggle *Fashion Product Images (Small)* dataset (scraped from Myntra around 2011–2016 for computer vision research). The dataset provided image files and metadata columns (`id`, `gender`, `masterCategory`, `subCategory`, `articleType`, `baseColour`, `season`, `year`, `usage`, `productDisplayName`), but **never included product page URLs, affiliate links, or e-commerce store URLs**.
2. **Intentional Cleansing:** Synthetic placeholder URLs (e.g. `demo-store.example.com`) were purged from the database in prior hardening steps because they led to non-existent 404 domains.
3. **Strict Validation:** Both backend (`sanitize_product_url`) and frontend (`isGenuineExternalUrl`) intentionally reject empty or synthetic URLs, resulting in `product_url = ""` and triggering the graceful fallback state `"Store Link Unavailable"`.

### 4.2 Available Product Metadata
Every product record in `fashion.db` and `data/deepfashion_metadata.json` possesses rich metadata:
- **`id`:** Numeric identifier (e.g., `15970`, `39386`, `59263`).
- **`name` / `productDisplayName`:** Detailed title (e.g., *"Turtle Check Men Navy Blue Shirt"*, *"CASIO G-Shock Men Black Digital Watch G-7710-1DR G223"*, *"Peter England Men Party Blue Jeans"*).
- **`brand`:** Extracted/normalized brand (e.g., *Nike, Adidas, Puma, FabIndia, Peter England, Fossil, Titan, Casio, Levi's, Biba, Jealous 21, Baggit*).
- **`category` & `subcategory`:** Canonical categories (*Shirt, T-Shirt, Jeans, Trousers, Dress, Saree, Kurta, Jacket, Hoodie, Sweater, Shoes, Sneakers, Accessories*).
- **`article_type`:** Granular article types (*Shirts, Tshirts, Watches, Handbags, Flip Flops, Casual Shoes, Formal Shoes, Belts, Wallets, etc.*).
- **`gender`:** *Men, Women, Boys, Girls, Unisex*.
- **`color`:** *Black, White, Blue, Navy, Gray, Red, Green, Pink, Purple, Beige, Olive, Brown, Burgundy, Yellow, Orange, Patterned*.
- **`style` / `usage`:** *Casual, Formal, Sporty, Traditional, Party*.
- **`pattern`:** *Solid, Striped, Checked, Floral, Printed, Patterned*.
- **`price` & `discount_price`:** Realistic INR pricing.
- **`image_url`:** High-resolution local image serving path (`/uploads/deepfashion/{id}.jpg`).

### 4.3 Missing Data
- **Direct canonical e-commerce product URLs** (e.g., live Myntra, Amazon, or brand product landing URLs for historic 2011–2016 SKUs).
- **Merchant/Store identifier** (all currently labeled `platform: "DeepFashion"` or `platform: "Demo Store"`).

---

## 5. Feasibility & Product Mapping Analysis

### Can products realistically be mapped to external e-commerce destinations?
**Yes.** While historic 2011–2016 individual product SKU pages may be archived or discontinued on specific retail websites, every product has a high-precision search signature composed of:
`{Brand} + {Gender} + {Color} + {Article Type / Product Name}`

Products can be mapped through three distinct, realistic tiers:

1. **Tier 1: Dynamic High-Intent E-Commerce / Search Query Links (Broad Catalog Coverage)**
   - For all 44,441 catalog items, generate clean, safe, parameterized search URLs to trusted fashion e-commerce / search platforms (e.g., Google Shopping, Myntra, Amazon Fashion, or Brand Official Search).
   - Example: `https://www.google.com/search?tbm=shop&q=Turtle+Men+Navy+Blue+Check+Shirt` or direct brand store search queries.
   - Fully dynamic, requires zero hardcoding of ephemeral SKU links, never returns 404 dead-ends.

2. **Tier 2: Direct E-Commerce Store & Brand Mapping for Known Brands**
   - For recognized brands in the catalog (*Puma, Adidas, Nike, Levi's, FabIndia, Fossil, Casio, Titan, Peter England*), map to brand e-commerce portals or brand catalog search endpoints.
   - Example: For Casio G-Shock -> `https://www.casio.com/in/watches/gshock/` or brand search query.

3. **Tier 3: Curated Direct E-Commerce Links for Showcase / Top-Match Items**
   - Provide a curated set of verified live e-commerce URLs for key showcase items or allow Admin dashboard manual entry/overrides.

---

## 6. Files That Will Need Modification (for Subsequent Implementation Phases)

| Component | File Path | Scope of Needed Modifications |
| :--- | :--- | :--- |
| **Backend Utility / Resolver** | `backend/app/services/url_resolver.py` *(New/Updated)* | URL generator / search query builder based on brand, name, category, and target store platform. |
| **Backend Schemas** | `backend/app/schemas/product.py` | Accommodate generated / resolved store URLs and platform badges. |
| **Backend API** | `backend/app/api/products.py` & `search.py` | Ensure resolved store link and platform are attached to product responses or dynamically computed. |
| **Data Ingestion / Enrichment Script** | `scripts/enrich_product_urls.py` *(New/Updated)* | Batch script to populate or enrich `product_url` and `platform` in SQLite `fashion.db` based on deterministic brand/name queries. |
| **Frontend Detail Page** | `frontend/src/pages/ProductDetailPage.tsx` | Enhanced "Visit Store / Buy Online" CTA with platform name and search provider indicator. |
| **Frontend Product Card** | `frontend/src/components/ProductCard.tsx` | Optional quick external link icon or platform pill badge. |
| **Frontend URL Utility** | `frontend/src/utils/url.ts` | Whitelist approved search and e-commerce domains (e.g., `google.com/search`, `amazon.in`, `myntra.com`, etc.). |
| **Tests** | `backend/tests/` & `scripts/test_view_product_flow.py` | Automated tests verifying URL generation, sanitization, and clickout flows. |

---

## 7. Audit Conclusion

The current product URL system is clean, secure, and devoid of broken placeholder links. The "Store Link Unavailable" state is functioning exactly as designed given the research origin of the DeepFashion dataset. With rich product names, brands, categories, and colors present across all 44,441 catalog records, the application is ideally positioned for a robust, multi-tier product URL resolution strategy.
