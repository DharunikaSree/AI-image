"""
Universal Shopping Destination Population Pipeline (Phase 8 Step 14)

Populates legitimate, actionable, and safe external shopping destinations for all 44,442
catalog products in fashion.db while strictly preserving existing verified exact product links.

Truthfulness Rules:
- exact_product:      verification_status = "verified",           availability_status = "available"
- official_store:     verification_status = "official_store",     availability_status = "unknown"
- shopping_search:    verification_status = "search_destination", availability_status = "unknown"
- fallback_search:    verification_status = "search_destination", availability_status = "unknown"

Usage:
    python scripts/populate_universal_shopping_destinations.py --dry-run --limit 100
    python scripts/populate_universal_shopping_destinations.py --report data/universal_shopping_destination_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.core.database import SessionLocal, engine, Base
from app.models.product import Product, ProductExternalLink
from app.services.shopping_destination_resolver import (
    ShoppingDestinationResolver,
    destination_resolver,
)
from app.services.product_link_matcher import is_valid_external_url


def populate_shopping_destinations(
    dry_run: bool = False,
    limit: int | None = None,
    start_id: int = 0,
    batch_size: int = 2000,
    report_path: str = "data/universal_shopping_destination_report.json",
) -> dict[str, Any]:
    out_report_file = PROJECT_ROOT / Path(report_path) if not Path(report_path).is_absolute() else Path(report_path)
    out_report_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("   UNIVERSAL SHOPPING DESTINATION POPULATION PIPELINE")
    print(f"   Mode:             {'DRY RUN (No DB modifications)' if dry_run else 'PRODUCTION POPULATION (Writing to DB)'}")
    print(f"   Limit:            {limit if limit is not None else 'ALL (44,442 Products)'}")
    print(f"   Batch Size:       {batch_size}")
    print(f"   Output Report:    {out_report_file.resolve()}")
    print("=" * 75)

    db = SessionLocal()
    resolver = ShoppingDestinationResolver()

    try:
        # 1. Identify existing verified exact product links to preserve
        print("\n[*] Scanning database for existing verified exact product links to preserve...")
        existing_verified_links = (
            db.query(ProductExternalLink)
            .filter(ProductExternalLink.verification_status == "verified")
            .all()
        )
        preserved_pids: set[int] = {l.product_id for l in existing_verified_links}
        preserved_count = len(preserved_pids)
        print(f"    -> Found {preserved_count} verified exact product links. These will remain 100% untouched.")

        # 2. Also map any other existing external links to avoid duplicate rows
        all_existing_links = (
            db.query(ProductExternalLink.product_id, ProductExternalLink.external_url)
            .all()
        )
        existing_link_pids: set[int] = {l[0] for l in all_existing_links}

        # 3. Query products to process
        print("[*] Loading catalog products...")
        query = db.query(Product).order_by(Product.id.asc())
        if start_id > 0:
            query = query.filter(Product.id >= start_id)
        if limit is not None and limit > 0:
            query = query.limit(limit)

        products = query.all()
        total_products_to_process = len(products)
        print(f"    -> Processing {total_products_to_process:,} products.")

        exact_count = 0
        official_store_count = 0
        shopping_search_count = 0
        fallback_search_count = 0
        unresolved_count = 0
        rejected_count = 0
        new_links_to_insert: list[dict[str, Any]] = []

        t_start = time.perf_counter()

        for idx, p in enumerate(products, start=1):
            # If product already has a verified exact link, preserve it as exact_product
            if p.id in preserved_pids:
                exact_count += 1
                continue

            # Run ShoppingDestinationResolver
            dest = resolver.resolve(p)

            # Security validation
            if not is_valid_external_url(dest.store_url):
                rejected_count += 1
                unresolved_count += 1
                continue

            # Classify destination type counts
            if dest.destination_type == "exact_product":
                exact_count += 1
                v_status = "verified"
                a_status = "available" if dest.store_available else "out_of_stock"
            elif dest.destination_type == "official_store":
                official_store_count += 1
                v_status = "official_store"
                a_status = "unknown"
            elif dest.destination_type == "shopping_search":
                shopping_search_count += 1
                v_status = "search_destination"
                a_status = "unknown"
            elif dest.destination_type == "fallback_search":
                fallback_search_count += 1
                v_status = "search_destination"
                a_status = "unknown"
            else:
                unresolved_count += 1
                continue

            # Prepare row for insertion if not already present in DB
            if p.id not in existing_link_pids:
                new_links_to_insert.append({
                    "product_id": p.id,
                    "store_name": dest.store_name,
                    "external_url": dest.store_url,
                    "verification_status": v_status,
                    "availability_status": a_status,
                    "destination_type": dest.destination_type,
                    "price_on_store": None,
                    "currency": "INR",
                    "is_primary": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })

        # Commit in batches if not dry run
        if not dry_run and new_links_to_insert:
            print(f"\n[*] Inserting {len(new_links_to_insert):,} new shopping destinations into database...")
            for i in range(0, len(new_links_to_insert), batch_size):
                batch = new_links_to_insert[i : i + batch_size]
                db.bulk_insert_mappings(ProductExternalLink, batch)
                db.commit()
                print(f"    -> Committed batch {i + len(batch):,} / {len(new_links_to_insert):,}")
            print("    -> All shopping destinations persisted successfully.")
        elif dry_run:
            print(f"\n[*] Dry Run complete: {len(new_links_to_insert):,} destinations generated (No database writes).")

        elapsed_sec = time.perf_counter() - t_start

        # Overall counts
        total_catalog_products = db.query(Product).count() if not dry_run else total_products_to_process

        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "total_processed": total_products_to_process,
            "total_catalog_products": total_catalog_products,
            "exact_product_destinations": exact_count,
            "official_store_destinations": official_store_count,
            "shopping_search_destinations": shopping_search_count,
            "fallback_destinations": fallback_search_count,
            "unresolved_products": unresolved_count,
            "rejected_destinations": rejected_count,
            "existing_verified_links_preserved": preserved_count,
            "elapsed_seconds": round(elapsed_sec, 2),
        }

        print("\n" + "=" * 75)
        print("   UNIVERSAL SHOPPING DESTINATION POPULATION REPORT")
        print("=" * 75)
        print(f"Total processed:                   {total_products_to_process:,}")
        print(f"Exact product destinations:        {exact_count:,}")
        print(f"Official store destinations:       {official_store_count:,}")
        print(f"Shopping search destinations:      {shopping_search_count:,}")
        print(f"Fallback destinations:             {fallback_search_count:,}")
        print(f"Unresolved products:               {unresolved_count:,}")
        print(f"Rejected destinations:             {rejected_count:,}")
        print(f"Existing verified links preserved: {preserved_count:,}")
        print(f"Processing time:                   {elapsed_sec:.2f}s")
        print("=" * 75)

        with open(out_report_file, "w", encoding="utf-8") as rf:
            json.dump(report_data, rf, indent=2)
        print(f"\n[OK] Report saved to: {out_report_file.resolve()}\n")

        return report_data

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Populate universal shopping destinations for all catalog products.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate population without database writes")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of products to process")
    parser.add_argument("--start-id", type=int, default=0, help="Starting product ID")
    parser.add_argument("--batch-size", type=int, default=2000, help="Database batch insert size")
    parser.add_argument("--report", type=str, default="data/universal_shopping_destination_report.json", help="Path to output report")

    args = parser.parse_args()
    populate_shopping_destinations(
        dry_run=args.dry_run,
        limit=args.limit,
        start_id=args.start_id,
        batch_size=args.batch_size,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()
