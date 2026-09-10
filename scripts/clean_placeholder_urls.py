"""
Data cleansing script to remove placeholder/demo external URLs
from fashion.db without modifying product records.
"""
import sqlite3
from pathlib import Path

POSSIBLE_DB_PATHS = [
    Path(__file__).resolve().parent.parent / "backend" / "fashion.db",
    Path(__file__).resolve().parent.parent / "fashion.db",
    Path(__file__).resolve().parent.parent / "backend" / "fashion_search.db",
]

def clean_urls():
    found = False
    for DB_PATH in POSSIBLE_DB_PATHS:
        if not DB_PATH.exists():
            continue
        found = True
        print(f"\nProcessing database at: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*) FROM products 
            WHERE product_url LIKE '%demo-store%' 
               OR product_url LIKE '%example.com%' 
               OR product_url LIKE '%localhost%'
               OR product_url LIKE '%127.0.0.1%'
        """)
        placeholder_count = cur.fetchone()[0]
        print(f"Found {placeholder_count} products with placeholder URLs.")

        if placeholder_count > 0:
            cur.execute("""
                UPDATE products 
                SET product_url = ''
                WHERE product_url LIKE '%demo-store%' 
                   OR product_url LIKE '%example.com%' 
                   OR product_url LIKE '%localhost%'
                   OR product_url LIKE '%127.0.0.1%'
            """)
            conn.commit()
            print(f"Successfully cleaned {placeholder_count} product records. Set product_url = ''")

        # Verify
        cur.execute("SELECT COUNT(*) FROM products WHERE product_url != ''")
        remaining_valid = cur.fetchone()[0]
        print(f"Remaining products with non-empty product_url: {remaining_valid}")

        cur.execute("SELECT id, name, product_url, platform FROM products WHERE id=30239")
        item_30239 = cur.fetchone()
        if item_30239:
            print(f"Product 30239 verification: {item_30239}")

        conn.close()

    if not found:
        print("No database files found.")

if __name__ == "__main__":
    clean_urls()
