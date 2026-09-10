"""
Migration and Database Verification Script for Product External Links (Phase 8 Step 3)

Creates the `product_external_links` table with all required columns, constraints,
and indexes without affecting any existing product records or inserting fake URLs.
"""
from __future__ import annotations

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.core.database import Base, engine, SessionLocal
from app.models.product import Product, ProductExternalLink


POSSIBLE_DB_PATHS = [
    BACKEND_DIR / "fashion.db",
    PROJECT_ROOT / "fashion.db",
]


def run_migration():
    print("=" * 75)
    print("   PHASE 8 STEP 3: PRODUCT EXTERNAL LINKS DATABASE MIGRATION")
    print("=" * 75)

    # 1. Run SQLAlchemy metadata creation (safe idempotent table creation)
    print("\n[*] Initializing SQLAlchemy metadata...")
    Base.metadata.create_all(bind=engine)
    print("    -> Base.metadata.create_all completed successfully.")

    # 2. Inspect and ensure schema on SQLite database files directly
    for db_path in POSSIBLE_DB_PATHS:
        if not db_path.exists():
            continue

        print(f"\n[*] Applying and validating schema on: {db_path}")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Enable Foreign Keys
        cur.execute("PRAGMA foreign_keys = ON;")

        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS product_external_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                store_name VARCHAR(80) NOT NULL,
                external_url VARCHAR(1000) NOT NULL,
                verification_status VARCHAR(30) DEFAULT 'unverified',
                last_verified_at DATETIME,
                availability_status VARCHAR(30) DEFAULT 'unknown',
                price_on_store FLOAT,
                currency VARCHAR(10) DEFAULT 'INR',
                is_primary BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)

        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS ix_product_external_links_product_id ON product_external_links (product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_product_external_links_store_name ON product_external_links (store_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_product_external_links_verification_status ON product_external_links (verification_status);")

        conn.commit()

        # Verify Table Info
        cur.execute("PRAGMA table_info(product_external_links);")
        columns = cur.fetchall()
        print(f"    Table 'product_external_links' columns ({len(columns)}):")
        for col in columns:
            cid, name, col_type, notnull, dflt, pk = col
            pk_flag = " [PK]" if pk else ""
            req_flag = " NOT NULL" if notnull else ""
            dflt_str = f" DEFAULT {dflt}" if dflt is not None else ""
            print(f"      - {name}: {col_type}{pk_flag}{req_flag}{dflt_str}")

        # Verify Indexes
        cur.execute("PRAGMA index_list(product_external_links);")
        indexes = cur.fetchall()
        print(f"    Indexes ({len(indexes)}):")
        for idx in indexes:
            print(f"      - {idx[1]} (unique={idx[2]})")

        # Verify Existing Products Preservation
        cur.execute("SELECT COUNT(*) FROM products;")
        total_products = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products WHERE product_url != '' AND product_url IS NOT NULL;")
        non_empty_legacy_urls = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM product_external_links;")
        total_links = cur.fetchone()[0]

        print(f"\n    [Integrity Check]")
        print(f"      Total products preserved: {total_products}")
        print(f"      Products with legacy non-empty URLs: {non_empty_legacy_urls}")
        print(f"      Total product external links: {total_links}")

        conn.close()

    # 3. Test SQLAlchemy ORM Relationship
    print("\n[*] Validating SQLAlchemy ORM integration...")
    db = SessionLocal()
    try:
        sample_product = db.query(Product).first()
        if sample_product:
            print(f"    Sample Product loaded: #{sample_product.id} - '{sample_product.name}'")
            print(f"    Relationship `sample_product.external_links`: {sample_product.external_links}")
            assert isinstance(sample_product.external_links, list), "external_links must be a list"
            print("    -> ORM relationship verified successfully (PASSED)")
        else:
            print("    [!] Warning: No products found in database.")
    finally:
        db.close()

    print("\n" + "=" * 75)
    print("   MIGRATION & VALIDATION COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_migration()
