# Phase 8 — Step 4: Product Link Ingestion Pipeline Documentation

**Project:** Lumière AI Fashion Search  
**Component:** Data Ingestion Pipeline & Link Verification  
**Script:** `scripts/import_product_links.py`  
**Sample Feed:** `data/product_links.example.csv`  
**Date:** August 2026

---

## 1. Overview & Ethical Ingestion Principles

The Product Link Ingestion Pipeline provides a robust, production-safe mechanism for importing genuine external e-commerce product links into the Lumière database (`fashion.db`).

### Ethical & Legal Compliance:
- **No Unsolicited Scraping:** The system does **not** perform automated web scraping that violates merchant Terms of Service or `robots.txt` policies.
- **Authorized Sources Only:** Links must originate from legitimate sources:
  1. Official retailer APIs & developer portals (e.g. Myntra, Amazon, Flipkart, Tata CLiQ, Ajio).
  2. Licensed fashion product datasets & catalog feeds.
  3. Official affiliate network data feeds.
  4. Verified manually curated CSV feeds.
- **Zero URL Hallucination:** URLs are never synthesized, guessed from product titles, or fabricated.

---

## 2. Ingestion Pipeline Architecture

```
[Authorized Source Feed (CSV)]
              │
              ▼
[scripts/import_product_links.py]
              │
              ├─► 1. Foreign Key Verification (Must exist in products table)
              ├─► 2. HTTPS Scheme Enforcement (Strict reject of http://, javascript:, etc.)
              ├─► 3. Hostname & TLD Validation (Must have valid netloc & TLD)
              ├─► 4. Blacklist & Demo Filter (Rejects example.com, demo-store, localhost)
              ├─► 5. SSRF & IP Protection (Rejects private/loopback IP literals)
              ├─► 6. Duplicate Detection (Checked against batch & existing DB records)
              │
              ▼
  ┌───────────────────────┴───────────────────────┐
  │                                               │
  ▼                                               ▼
[Valid Records]                              [Rejected Records]
  • Stored in `product_external_links`         • Logged to console with line #
  • Status: `unverified` or `verified`         • Explicit rejection reason
```

---

## 3. CSV File Specification

Input CSV files must be formatted in UTF-8 (or UTF-8-SIG). The header row is required.

### 3.1 Required Columns

| Column Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `product_id` | Integer | ID of an existing item in `products` table | `15970` |
| `store_name` | String | Name of the retailer / store | `Myntra` |
| `external_url` | String | Full HTTPS product landing URL (max 1000 chars) | `https://www.myntra.com/...` |

### 3.2 Optional Columns

| Column Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `product_name` | String | Product display name for logging/reference | `Turtle Check Navy Blue Shirt` |
| `brand` | String | Brand name | `Turtle` |
| `category` | String | Clothing category | `Shirt` |
| `price` | Float | Live price on merchant store in INR | `1799.0` |
| `availability_status` | String | Initial stock state (`in_stock`, `unknown`) | `in_stock` |

---

## 4. Strict Validation & Rejection Rules

Every row is evaluated against strict integrity checks. A failure at any step causes immediate rejection with a descriptive reason logged:

1. **Foreign Key Integrity:** `product_id` must parse as an integer and match an existing row in `products`. Non-existent product IDs are rejected (*e.g., Row 10: `Product ID #999999 does not exist in catalog database`*).
2. **HTTPS Protocol:** URLs must begin with `https://`. Insecure `http://` or non-standard schemes (`javascript:`, `data:`, `file:`) are rejected (*e.g., Row 11: `Insecure HTTP protocol (HTTPS required)`*).
3. **Domain Blacklist & Demo Filtering:** URLs containing blocked domains (`example.com`, `demo-store.example.com`, `localhost`, `test.com`, `*.local`) are rejected (*e.g., Row 12: `Blocked or demo hostname: demo-store.example.com`*).
4. **SSRF Protection:** Numeric IP hostnames (such as `127.0.0.1`, `192.168.x.x`, `10.x.x.x`, `169.254.x.x`) are rejected.
5. **Duplicate Prevention:** URLs matching an existing `(product_id, external_url)` pair in the database or earlier in the same CSV batch are skipped.

---

## 5. CLI Usage & Commands

The ingestion tool provides flexible execution options:

### 5.1 Dry Run (Validate without modifying database)
```bash
python scripts/import_product_links.py --csv data/product_links.example.csv --dry-run
```

### 5.2 Production Ingestion (Default: unverified status)
```bash
python scripts/import_product_links.py --csv data/verified_partner_feed.csv
```

### 5.3 Authenticated Feed Ingestion (Directly mark as verified)
```bash
python scripts/import_product_links.py --csv data/authorized_brand_feed.csv --mark-verified
```

---

## 6. Execution Output & Audit Sample

Running `python scripts/import_product_links.py --csv data/product_links.example.csv --dry-run` yields:

```
===========================================================================
   PRODUCT LINK INGESTION PIPELINE
   Source CSV: data/product_links.example.csv
   Dry Run:    ENABLED (No DB changes)
   Status:     unverified
===========================================================================

[*] Indexing catalog products from database...
    Loaded 44,442 valid catalog product IDs.
[*] Indexing existing product links from database...
    Loaded 0 existing external links.

[*] Processing CSV records...

[*] Dry Run complete: 8 links validated (No DB changes made).

===========================================================================
   INGESTION SUMMARY REPORT
===========================================================================
   Total rows processed:         11
   Successfully imported:        8
   Rejected (Invalid/Missing):   3
   Duplicate links skipped:      0
   Total valid links in DB now:  0
===========================================================================

[!] Sample of Rejected Records (3 of 3):
    - Row 10: PID=999999 | Reason: Product ID #999999 does not exist in catalog database | URL: https://www.amazon.in/sample-nonexistent-item/dp/B00000000
    - Row 11: PID=15970 | Reason: Insecure HTTP protocol (HTTPS required) | URL: http://www.myntra.com/insecure-link/15970
    - Row 12: PID=39386 | Reason: Blocked or demo hostname: demo-store.example.com | URL: https://demo-store.example.com/product/39386
```

---

## 7. Sample Feed Reference

The reference example CSV is located at:
`data/product_links.example.csv`

It contains representative rows illustrating both valid merchant URLs and intentional invalid test cases for pipeline verification.
