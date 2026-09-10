"""
Migrate Fashion Product Catalog to High-Resolution Images.
Dataset: paramaggarwal/fashion-product-images-dataset (Downloaded to Drive D:).
"""
from __future__ import annotations

import os
import sys
import glob
import time
import sqlite3
from pathlib import Path
from PIL import Image

# Route KaggleHub cache to Drive D: where 274 GB of free space is available
os.environ["KAGGLEHUB_CACHE"] = r"D:\kagglehub_cache"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_PATH = BACKEND_DIR / "fashion.db"

def run_migration():
    print("=" * 75)
    print("   Upgrading Fashion Product Images to High Resolution")
    print("=" * 75)

    if not DB_PATH.exists():
        print(f"[!] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT count(*), count(distinct id) FROM products")
    total_products, distinct_ids = cur.fetchone()
    print(f"[*] Total products in database: {total_products}")

    # 1. Access high-resolution dataset using KaggleHub on Drive D:
    print(f"[*] KaggleHub Cache Target: {os.environ['KAGGLEHUB_CACHE']}")
    print("[*] Downloading / Verifying paramaggarwal/fashion-product-images-dataset on Drive D:...")
    
    import kagglehub
    try:
        dataset_path = kagglehub.dataset_download("paramaggarwal/fashion-product-images-dataset")
        print(f"[+] High-Res Dataset successfully accessed at: {dataset_path}")
    except Exception as e:
        print(f"[!] KaggleHub download error: {e}")
        dataset_path = None

    if not dataset_path or not os.path.exists(dataset_path):
        print("[!] Could not access high-resolution dataset.")
        conn.close()
        return

    # Find the images directory inside the downloaded dataset
    possible_img_dirs = [
        Path(dataset_path) / "images",
        Path(dataset_path) / "fashion-dataset" / "images",
        Path(dataset_path) / "fashion_dataset" / "images",
        Path(dataset_path),
    ]

    images_dir = None
    for p in possible_img_dirs:
        if p.exists() and len(list(p.glob("*.jpg"))) > 100:
            images_dir = p
            break

    if not images_dir:
        all_jpgs = list(Path(dataset_path).rglob("*.jpg"))
        if all_jpgs:
            images_dir = all_jpgs[0].parent

    if not images_dir:
        print("[!] Could not locate images directory in dataset.")
        conn.close()
        return

    print(f"[+] Found High-Res Images Directory: {images_dir}")

    # 2. Inspect sample images and report dimensions
    sample_files = list(images_dir.glob("*.jpg"))[:10]
    sample_info = []
    for sf in sample_files:
        try:
            with Image.open(sf) as img:
                sample_info.append((sf.name, img.size))
        except Exception:
            pass

    print("\n--- High-Resolution Image Dimensions ---")
    for name, size in sample_info[:8]:
        print(f"  - {name}: {size[0]} × {size[1]} px")

    # 3. Verify ID matching against SQLite database
    cur.execute("SELECT id FROM products")
    db_ids = [row[0] for row in cur.fetchall()]
    
    matched_count = 0
    missing_count = 0
    
    for pid in db_ids:
        img_file = images_dir / f"{pid}.jpg"
        if img_file.exists():
            matched_count += 1
        else:
            missing_count += 1

    print(f"\n[*] Matching Summary:")
    print(f"  - Total DB Products: {len(db_ids)}")
    print(f"  - High-Res Matches : {matched_count} ({matched_count/len(db_ids)*100:.1f}%)")
    print(f"  - Missing High-Res : {missing_count}")

    conn.close()
    return str(images_dir)

if __name__ == "__main__":
    run_migration()
