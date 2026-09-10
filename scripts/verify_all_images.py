"""
Verify high-res file availability and resolution for all 44,441 products.
"""
import os
import sys
import sqlite3
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import HIGH_RES_CANDIDATE_DIRS, SMALL_RES_DIR

conn = sqlite3.connect(str(BACKEND_DIR / "fashion.db"))
cur = conn.cursor()
cur.execute("SELECT id, name, image_url FROM products")
rows = cur.fetchall()
conn.close()

print(f"Total products in DB: {len(rows)}")

found_high_res = 0
found_small = 0
missing_all = 0

sample_dims = {}

for pid, name, img_url in rows:
    filename = Path(img_url).name
    
    # Check high res
    hr_file = None
    for hdir in HIGH_RES_CANDIDATE_DIRS:
        cand = hdir / filename
        if cand.exists():
            hr_file = cand
            break
            
    if hr_file:
        found_high_res += 1
        if len(sample_dims) < 10:
            try:
                with Image.open(hr_file) as im:
                    sample_dims[filename] = im.size
            except Exception:
                pass
    elif SMALL_RES_DIR.exists() and (SMALL_RES_DIR / filename).exists():
        found_small += 1
    else:
        missing_all += 1

print(f"High-Res Matches : {found_high_res} / {len(rows)} ({found_high_res/len(rows)*100:.2f}%)")
print(f"Small-Res Only   : {found_small}")
print(f"Missing Entirely : {missing_all}")
print(f"\nSample Dimensions:")
for fn, size in sample_dims.items():
    print(f"  - {fn}: {size[0]} × {size[1]} px")
