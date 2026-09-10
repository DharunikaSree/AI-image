"""
Normalize Windows backslashes in search_history.image_path to forward slashes.
This ensures all uploaded garment images and past search attachments load correctly.
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "fashion.db"

def main():
    if not DB_PATH.exists():
        print(f"[!] Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT id, image_path FROM search_history")
    rows = cur.fetchall()
    
    updated_count = 0
    for rid, path in rows:
        if path and "\\" in path:
            normalized = path.replace("\\", "/")
            cur.execute("UPDATE search_history SET image_path = ? WHERE id = ?", (normalized, rid))
            updated_count += 1

    conn.commit()
    print(f"[OK] Successfully checked {len(rows)} rows, updated {updated_count} rows with forward slashes.")

    # Verify a few samples
    cur.execute("SELECT id, image_path FROM search_history ORDER BY id DESC LIMIT 5")
    sample_rows = cur.fetchall()
    print("[*] Sample updated rows:")
    for rid, path in sample_rows:
        print(f"    - ID {rid}: {path}")

    conn.close()

if __name__ == "__main__":
    main()
