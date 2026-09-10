"""
Safe migration script to add destination_type column to product_external_links table if missing.
"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings

settings = get_settings()


def run_migration():
    db_path = settings.DATABASE_URL
    if "sqlite:///" in db_path:
        db_file = Path(db_path.replace("sqlite:///", ""))
        if not db_file.is_absolute():
            db_file = BACKEND_DIR / db_file
    else:
        db_file = BACKEND_DIR / "fashion.db"

    if not db_file.exists():
        print(f"Database file not found at {db_file}")
        return

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(product_external_links)")
    columns = [row[1] for row in cursor.fetchall()]

    if "destination_type" not in columns:
        print("Adding column 'destination_type' to product_external_links...")
        cursor.execute("ALTER TABLE product_external_links ADD COLUMN destination_type VARCHAR(30) DEFAULT 'exact_product'")
        conn.commit()
        print("Column 'destination_type' added successfully.")
    else:
        print("Column 'destination_type' already exists.")

    conn.close()


if __name__ == "__main__":
    run_migration()
