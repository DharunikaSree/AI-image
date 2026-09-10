"""
Import DeepFashion 44,441 catalog records into SQLite fashion.db.
Maintains existing demo user & admin accounts while replacing placeholder
demo store items with real DeepFashion products.
"""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User, UserPreference  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
METADATA_PATH = DATA_DIR / "deepfashion_metadata.json"

# Category standardization map
CATEGORY_MAP = {
    "Casual Shoes": "Shoes",
    "Sports Shoes": "Shoes",
    "Formal Shoes": "Shoes",
    "Heels": "Shoes",
    "Flats": "Shoes",
    "Sandals": "Shoes",
    "Flip Flops": "Shoes",
    "Sneakers": "Shoes",
    "Shoes": "Shoes",
    "Shirts": "Shirt",
    "Shirt": "Shirt",
    "Tshirts": "T-Shirt",
    "T-Shirt": "T-Shirt",
    "Tops": "Shirt",
    "Tunics": "Shirt",
    "Kurtas": "Kurta",
    "Kurta": "Kurta",
    "Kurtis": "Kurta",
    "Dresses": "Dress",
    "Dress": "Dress",
    "Sarees": "Saree",
    "Saree": "Saree",
    "Jeans": "Jeans",
    "Trousers": "Trousers",
    "Track Pants": "Trousers",
    "Shorts": "Shorts",
    "Skirts": "Skirts",
    "Skirt": "Skirts",
    "Jackets": "Jacket",
    "Jacket": "Jacket",
    "Sweaters": "Sweater",
    "Sweater": "Sweater",
    "Sweatshirts": "Hoodie",
    "Hoodies": "Hoodie",
    "Hoodie": "Hoodie",
    "Watches": "Watches",
    "Handbags": "Handbags",
    "Clutches": "Handbags",
    "Backpacks": "Handbags",
    "Wallets": "Handbags",
}


def run():
    print("=" * 70)
    print("   Importing DeepFashion Catalog into SQLite fashion.db")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Load metadata
        print(f"[*] Loading metadata from: {METADATA_PATH}")
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        total = len(metadata)
        print(f"    Loaded {total} metadata records.")

        # Check existing count
        existing_count = db.query(Product).count()
        print(f"[*] Current products in database: {existing_count}")

        # Clear existing old placeholder products
        if existing_count > 0:
            print("[*] Refreshing product catalog table with real DeepFashion items...")
            db.query(Product).delete()
            db.commit()

        print("[*] Inserting 44,441 DeepFashion products in batches...")
        start_time = time.time()
        batch_size = 5000
        products_batch = []
        count = 0

        for item in metadata:
            raw_cat = item.get("category", "")
            raw_art = item.get("article_type", "")

            # Normalize category
            category = CATEGORY_MAP.get(raw_art, CATEGORY_MAP.get(raw_cat, raw_cat or "Other"))
            color = item.get("base_colour", "Multi")
            usage = item.get("usage", "Casual")
            gender = item.get("gender", "Unisex")
            brand = item.get("brand", "DeepFashion")
            name = item.get("name", f"{color} {category}")

            # Realistic price derivation
            base_price = float(item.get("price", 1499.0))
            if base_price <= 0:
                base_price = 1299.0

            discount = float(round(base_price * 0.80, 0)) if item["id"] % 3 == 0 else None

            # Pattern detection from name
            lower_name = name.lower()
            if any(w in lower_name for w in ["printed", "print", "stripe", "striped", "check", "checked", "graphic", "polka", "floral", "embroidered", "embroidery"]):
                pattern = "Patterned"
            else:
                pattern = "Solid"

            group_key = f"{raw_art}-{gender}".lower().replace(" ", "-").replace("/", "-")

            product = Product(
                id=item["id"],
                name=name,
                description=f"{gender} {usage} {raw_art or category} in {color}, high quality DeepFashion catalog item.",
                brand=brand,
                category=category,
                subcategory=raw_art or category,
                style=usage or "Casual",
                color=color or "Multi",
                pattern=pattern,
                price=base_price,
                discount_price=discount,
                currency="INR",
                image_url=f"/uploads/deepfashion/{item['id']}.jpg",
                product_url="",
                platform="DeepFashion",
                availability=True,
                embedding_reference="",
                group_key=group_key,
            )
            products_batch.append(product)
            count += 1

            if len(products_batch) >= batch_size:
                db.bulk_save_objects(products_batch)
                db.commit()
                products_batch = []
                print(f"    Inserted {count}/{total} products...", flush=True)

        if products_batch:
            db.bulk_save_objects(products_batch)
            db.commit()
            print(f"    Inserted {count}/{total} products...", flush=True)

        elapsed = time.time() - start_time
        print(f"[+] Successfully inserted {count} DeepFashion products into fashion.db in {elapsed:.2f}s!")

        # Ensure demo users exist
        if not db.query(User).filter(User.email == "demo@fashionai.dev").first():
            user = User(name="Demo User", email="demo@fashionai.dev", password_hash=hash_password("demo1234"))
            db.add(user)
            db.flush()
            db.add(UserPreference(user_id=user.id, preferred_styles="Casual,Party", preferred_colors="Black,Navy", budget_min=0, budget_max=5000))
            db.commit()
            print("[+] Verified demo user: demo@fashionai.dev")

        if not db.query(User).filter(User.email == "admin@fashionai.dev").first():
            admin = User(name="Demo Admin", email="admin@fashionai.dev", password_hash=hash_password("admin1234"), is_admin=True)
            db.add(admin)
            db.flush()
            db.add(UserPreference(user_id=admin.id))
            db.commit()
            print("[+] Verified admin user: admin@fashionai.dev")

    finally:
        db.close()

if __name__ == "__main__":
    run()
