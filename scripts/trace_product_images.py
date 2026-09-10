"""
Trace exact product image serving flow for requested products.
"""
from __future__ import annotations

import io
import os
import sys
import glob
import sqlite3
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app

def trace_product(query_name: str):
    conn = sqlite3.connect("fashion.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, image_url FROM products WHERE name LIKE ?", (f"%{query_name}%",))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"[!] No product found matching '{query_name}'")
        return

    pid, name, cat, db_image_url = rows[0]
    filename = Path(db_image_url).name
    frontend_url = f"http://localhost:8000{db_image_url}"

    print("=" * 75)
    print(f"Product: {name}")
    print(f"Product ID: {pid}")
    print(f"Database image_url: {db_image_url}")
    print(f"Frontend image URL: {frontend_url}")

    from app.core.config import get_settings
    settings = get_settings()

    # Check configured dataset directories
    candidate_paths = [d / filename for d in settings.dataset_image_dirs]

    print("\n--- Physical File Inspection on Disk ---")
    found_paths = []
    for cp in candidate_paths:
        exists = cp.exists()
        if exists:
            try:
                with Image.open(cp) as img:
                    dims = f"{img.size[0]} × {img.size[1]} px"
                    found_paths.append((cp, dims))
                    print(f"  [FOUND] {cp} -> Dimensions: {dims}")
            except Exception as e:
                print(f"  [FOUND but unreadable] {cp} ({e})")
        else:
            print(f"  [MISSING] {cp}")

    # Test HTTP response from FastAPI
    print("\n--- FastAPI HTTP Serving Test ---")
    client = TestClient(app)
    res = client.get(db_image_url)
    print(f"  HTTP GET {db_image_url} -> Status: {res.status_code}")
    print(f"  Content-Type: {res.headers.get('content-type')}")
    print(f"  Content-Length: {len(res.content)} bytes")

    if res.status_code == 200:
        try:
            served_img = Image.open(io.BytesIO(res.content))
            print(f"  Actual Dimensions of Image Served to Browser: {served_img.size[0]} × {served_img.size[1]} px")
            if served_img.size == (60, 80):
                print("  => Result: Browser receives 60×80 thumbnail.")
            elif served_img.size[0] > 500:
                print("  => Result: Browser receives HIGH-RESOLUTION image.")
            else:
                print(f"  => Result: Browser receives {served_img.size[0]}×{served_img.size[1]} image.")
        except Exception as e:
            print(f"  Could not decode image from response: {e}")

    print("=" * 75)

if __name__ == "__main__":
    trace_product("Reid & Taylor")
    print("\n")
    trace_product("Puma Men Future Cat")
