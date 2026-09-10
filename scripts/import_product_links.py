"""
Product Link Ingestion Pipeline for Lumière AI Fashion Search (Phase 8 Step 10)

Safely ingests legitimate external e-commerce product links from authorized CSV feeds,
curated partner datasets, or official retailer exports.

Enforces:
1. Strict URL validation (HTTPS only, anti-phishing, blocked domain blacklist).
2. Deduplication across database and batch entries.
3. Fake domain rejection (demo-store, example.com, localhost, private IPs).
4. Product-link matching confidence scoring via ProductLinkMatcher.
5. Record match confidence and reasons.
6. Optional URL verification via URLVerifier.
7. Verification status persistence.
8. Generation of detailed audit report (data/product_link_import_report.json).

Usage:
    python scripts/import_product_links.py --csv data/product_links.example.csv --mark-verified
    python scripts/import_product_links.py --csv data/product_links.example.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.core.database import SessionLocal, engine, Base
from app.models.product import Product, ProductExternalLink
from app.services.product_link_matcher import (
    ProductLinkMatcher,
    is_valid_external_url,
    DEFAULT_CONFIDENCE_THRESHOLD,
)
from app.services.url_verifier import (
    URLVerifier,
    prevalidate_url,
    is_private_or_blocked_host,
)


def import_product_links(
    csv_path: str | Path = "data/product_links.example.csv",
    dry_run: bool = False,
    mark_verified: bool = True,
    verify_online: bool = False,
    set_primary: bool = True,
    threshold: float = 0.70,
    report_path: str | Path = "data/product_link_import_report.json",
) -> dict[str, Any]:
    raw_path = Path(csv_path)
    if raw_path.is_absolute() and raw_path.exists():
        csv_file = raw_path
    elif (PROJECT_ROOT / raw_path).exists():
        csv_file = PROJECT_ROOT / raw_path
    elif raw_path.exists():
        csv_file = raw_path.resolve()
    else:
        raise FileNotFoundError(f"CSV file not found: {csv_path} (checked at {raw_path} and {PROJECT_ROOT / raw_path})")

    out_report_file = PROJECT_ROOT / Path(report_path) if not Path(report_path).is_absolute() else Path(report_path)
    out_report_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("   PRODUCT LINK INGESTION & VERIFICATION PIPELINE")
    print(f"   Source CSV:       {csv_file.resolve()}")
    print(f"   Dry Run:          {'ENABLED (No DB changes)' if dry_run else 'DISABLED (Writing to DB)'}")
    print(f"   Mark Verified:    {mark_verified}")
    print(f"   Verify Online:    {verify_online}")
    print(f"   Match Threshold:  {threshold}")
    print("=" * 75)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    total_rows = 0
    imported_count = 0
    rejected_urls_count = 0
    duplicate_count = 0
    match_failures_count = 0

    rejected_records: list[dict[str, Any]] = []
    match_failure_records: list[dict[str, Any]] = []
    imported_records: list[dict[str, Any]] = []

    matcher = ProductLinkMatcher(threshold=threshold)
    verifier = URLVerifier() if verify_online else None

    try:
        # 1. Preload catalog products for match scoring and foreign-key validation
        print("\n[*] Preloading catalog products from database for matching...")
        products_map: dict[int, Product] = {p.id: p for p in db.query(Product).all()}
        total_catalog_products = len(products_map)
        print(f"    Loaded {total_catalog_products:,} catalog products.")

        # 2. Preload existing links to prevent duplicates
        print("[*] Indexing existing product links from database...")
        existing_links = set(
            (r[0], r[1])
            for r in db.query(ProductExternalLink.product_id, ProductExternalLink.external_url).all()
        )
        print(f"    Loaded {len(existing_links):,} existing external links.")

        seen_in_batch: set[tuple[int, str]] = set()
        links_to_insert: list[ProductExternalLink] = []

        print("\n[*] Processing feed records with validation & matching...")
        with open(csv_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV file is empty or missing headers.")

            headers = [h.strip().lower() for h in reader.fieldnames if h]
            required_cols = {"product_id", "store_name", "external_url"}
            missing = required_cols - set(headers)
            if missing:
                raise ValueError(f"Missing required CSV column(s): {', '.join(missing)}")

            for row_idx, row in enumerate(reader, start=2):
                total_rows += 1

                pid_raw = row.get("product_id", "").strip()
                store_name = row.get("store_name", "").strip() or "Verified Store"
                external_url = row.get("external_url", "").strip()
                product_name = row.get("product_name", "").strip()
                brand = row.get("brand", "").strip()
                category = row.get("category", "").strip()
                price_raw = row.get("price", "").strip()
                avail_status = row.get("availability_status", "").strip() or "in_stock"

                # Step 1: Validate URL syntax and reject fake/blocked domains
                is_valid_syntax, syntax_reason = prevalidate_url(external_url)
                if not is_valid_syntax:
                    rejected_urls_count += 1
                    rejected_records.append({
                        "row": row_idx,
                        "product_id": pid_raw,
                        "url": external_url,
                        "store_name": store_name,
                        "reason": f"URL Validation Failed: {syntax_reason}",
                    })
                    continue

                if not is_valid_external_url(external_url):
                    rejected_urls_count += 1
                    rejected_records.append({
                        "row": row_idx,
                        "product_id": pid_raw,
                        "url": external_url,
                        "store_name": store_name,
                        "reason": "URL Safety Check Failed (Blocked domain or non-HTTPS)",
                    })
                    continue

                # Step 2: Validate integer product ID
                try:
                    product_id = int(pid_raw)
                except ValueError:
                    match_failures_count += 1
                    match_failure_records.append({
                        "row": row_idx,
                        "product_id": pid_raw,
                        "url": external_url,
                        "reason": f"Invalid integer product_id: '{pid_raw}'",
                    })
                    continue

                # Step 3: Check existence in catalog
                catalog_product = products_map.get(product_id)
                if not catalog_product:
                    match_failures_count += 1
                    match_failure_records.append({
                        "row": row_idx,
                        "product_id": product_id,
                        "url": external_url,
                        "reason": f"Product ID #{product_id} does not exist in catalog database",
                    })
                    continue

                # Step 4: Duplicate link check
                link_key = (product_id, external_url)
                if link_key in existing_links or link_key in seen_in_batch:
                    duplicate_count += 1
                    rejected_records.append({
                        "row": row_idx,
                        "product_id": product_id,
                        "url": external_url,
                        "store_name": store_name,
                        "reason": "Duplicate link (already exists for this product)",
                    })
                    continue

                # Step 5: Product-Link Match Confidence Scoring
                candidate_dict = {
                    "product_id": product_id,
                    "store_name": store_name,
                    "external_url": external_url,
                    "product_name": product_name or catalog_product.name,
                    "brand": brand or catalog_product.brand,
                    "category": category or catalog_product.category,
                }
                match_score, match_reasons = matcher.compute_match_confidence(catalog_product, candidate_dict)

                if match_score < threshold:
                    match_failures_count += 1
                    match_failure_records.append({
                        "row": row_idx,
                        "product_id": product_id,
                        "catalog_product": catalog_product.name,
                        "candidate_name": product_name,
                        "match_score": round(match_score, 3),
                        "reasons": match_reasons or ["Match score below threshold"],
                    })
                    continue

                # Step 6: Online Verification if requested
                now = datetime.now(timezone.utc)
                if verify_online and verifier:
                    ver_result = verifier.verify(external_url)
                    v_status = ver_result.verification_status
                    a_status = ver_result.availability_status
                    last_ver = ver_result.last_verified_at or now
                elif mark_verified:
                    v_status = "verified"
                    a_status = "available" if avail_status in ("in_stock", "available") else "out_of_stock"
                    last_ver = now
                else:
                    v_status = "unverified"
                    a_status = avail_status
                    last_ver = None

                seen_in_batch.add(link_key)

                price_val = None
                if price_raw:
                    try:
                        price_val = float(price_raw)
                    except ValueError:
                        price_val = None

                link_obj = ProductExternalLink(
                    product_id=product_id,
                    store_name=store_name,
                    external_url=external_url,
                    verification_status=v_status,
                    last_verified_at=last_ver,
                    availability_status=a_status,
                    price_on_store=price_val,
                    currency="INR",
                    is_primary=set_primary,
                )
                links_to_insert.append(link_obj)
                imported_count += 1

                imported_records.append({
                    "product_id": product_id,
                    "product_name": catalog_product.name,
                    "store_name": store_name,
                    "external_url": external_url,
                    "match_score": round(match_score, 3),
                    "match_reasons": match_reasons,
                    "verification_status": v_status,
                    "availability_status": a_status,
                })

        # Step 7: Commit to database
        if not dry_run and links_to_insert:
            print(f"\n[*] Inserting {len(links_to_insert):,} validated and matched links into database...")
            db.bulk_save_objects(links_to_insert)
            db.commit()
            print("    -> Database commit completed successfully.")
        elif dry_run:
            print(f"\n[*] Dry Run complete: {len(links_to_insert):,} links validated and matched (No DB changes made).")

        # Step 8: Calculate overall catalog statistics
        verified_count = (
            db.query(ProductExternalLink.product_id)
            .filter(ProductExternalLink.verification_status == "verified")
            .distinct()
            .count()
        )
        unverified_count = (
            db.query(ProductExternalLink.product_id)
            .filter(ProductExternalLink.verification_status != "verified")
            .distinct()
            .count()
        )
        products_with_any_links = (
            db.query(ProductExternalLink.product_id)
            .distinct()
            .count()
        )
        products_without_links = max(0, total_catalog_products - products_with_any_links)

        # Step 9: Print requested console summary
        print("\n" + "=" * 75)
        print("   PRODUCT LINK INGESTION REPORT")
        print("=" * 75)
        print(f"Total catalog products:             {total_catalog_products:,}")
        print(f"Products with verified store links: {verified_count:,}")
        print(f"Products with unverified links:     {unverified_count:,}")
        print(f"Products without links:             {products_without_links:,}")
        print(f"Rejected URLs:                      {rejected_urls_count:,}")
        print(f"Duplicate links:                    {duplicate_count:,}")
        print(f"Match failures:                     {match_failures_count:,}")
        print("=" * 75)

        # Step 10: Generate JSON report file
        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "csv_source": str(csv_file.resolve()),
            "dry_run": dry_run,
            "total_catalog_products": total_catalog_products,
            "products_with_verified_store_links": verified_count,
            "products_with_unverified_links": unverified_count,
            "products_without_links": products_without_links,
            "rejected_urls": rejected_urls_count,
            "duplicate_links": duplicate_count,
            "match_failures": match_failures_count,
            "imported_links_count": len(links_to_insert),
            "imported_records": imported_records,
            "rejected_records": rejected_records,
            "match_failure_records": match_failure_records,
        }

        with open(out_report_file, "w", encoding="utf-8") as rf:
            json.dump(report_data, rf, indent=2)
        print(f"\n[OK] Audit report generated at: {out_report_file.resolve()}\n")

        return report_data

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Populate and match real e-commerce store links into catalog.")
    parser.add_argument("--csv", type=str, default="data/product_links.example.csv", help="Path to input CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Validate input without committing to database")
    parser.add_argument("--mark-verified", action="store_true", default=True, help="Mark valid imported links as verified")
    parser.add_argument("--unverified", action="store_true", help="Import links with unverified status")
    parser.add_argument("--verify", action="store_true", help="Perform online live URL probing before saving")
    parser.add_argument("--threshold", type=float, default=0.70, help="Matching confidence threshold (0.0 - 1.0)")
    parser.add_argument("--report", type=str, default="data/product_link_import_report.json", help="Path to output JSON report")
    parser.add_argument("--unset-primary", action="store_true", help="Do not mark ingested links as primary")

    args = parser.parse_args()
    import_product_links(
        csv_path=args.csv,
        dry_run=args.dry_run,
        mark_verified=not args.unverified,
        verify_online=args.verify,
        set_primary=not args.unset_primary,
        threshold=args.threshold,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()
