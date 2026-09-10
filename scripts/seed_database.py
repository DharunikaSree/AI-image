"""
Seeds the database with a deterministic demo product catalog.

Product "photos" are generated locally as solid-color swatches with PIL
(no scraping, no copyrighted images, no external network calls), which is
exactly why every seeded product also gets a real, meaningful embedding:
color-based visual search actually works out of the box.

Usage:
    cd backend
    python ../scripts/seed_database.py
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from PIL import Image, ImageDraw  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User, UserPreference  # noqa: E402
from app.services.embedding import embedding_service  # noqa: E402

COLOR_RGB = {
    "Black": (25, 25, 25), "White": (245, 245, 245), "Beige": (222, 202, 173),
    "Gray": (128, 128, 128), "Navy": (30, 40, 80), "Blue": (50, 90, 200),
    "Red": (200, 40, 40), "Burgundy": (110, 30, 45), "Green": (50, 130, 70),
    "Olive": (110, 110, 50), "Yellow": (220, 200, 60), "Orange": (220, 120, 40),
    "Pink": (230, 150, 180), "Brown": (110, 70, 40), "Purple": (110, 60, 140),
}

CATALOG = [
    # (name, category, style, brand, base_price, group)
    ("Classic Crew T-Shirt", "T-Shirt", "Casual", "Urban Basics", 399, "tshirt-crew"),
    ("Oversized Streetwear Tee", "T-Shirt", "Streetwear", "Northline", 599, "tshirt-oversized"),
    ("Slim Fit Formal Shirt", "Shirt", "Formal", "Everett & Co.", 1299, "shirt-slimfit"),
    ("Linen Casual Shirt", "Shirt", "Casual", "CoastalWear", 999, "shirt-linen"),
    ("Skinny Fit Jeans", "Jeans", "Casual", "DenimLab", 1599, "jeans-skinny"),
    ("Straight Fit Jeans", "Jeans", "Minimal", "DenimLab", 1499, "jeans-straight"),
    ("Wide Leg Trousers", "Trousers", "Minimal", "Studio Form", 1799, "trouser-wide"),
    ("Tailored Formal Trousers", "Trousers", "Formal", "Everett & Co.", 1899, "trouser-formal"),
    ("V-Neck Midi Dress", "Dress", "Party", "Bellerose", 2499, "dress-midi"),
    ("Wrap Casual Dress", "Dress", "Casual", "Bellerose", 1899, "dress-wrap"),
    ("Traditional Anarkali Dress", "Dress", "Traditional", "Heritage Loom", 3499, "dress-anarkali"),
    ("A-Line Party Dress", "Dress", "Party", "Vera Nova", 2999, "dress-aline"),
    ("Pleated Mini Skirt", "Skirt", "Party", "Vera Nova", 1199, "skirt-mini"),
    ("Denim A-Line Skirt", "Skirt", "Casual", "DenimLab", 999, "skirt-denim"),
    ("Cargo Shorts", "Shorts", "Streetwear", "Northline", 899, "shorts-cargo"),
    ("Tailored Shorts", "Shorts", "Minimal", "Studio Form", 799, "shorts-tailored"),
    ("Bomber Jacket", "Jacket", "Streetwear", "Northline", 2199, "jacket-bomber"),
    ("Trench Coat Jacket", "Jacket", "Formal", "Everett & Co.", 3299, "jacket-trench"),
    ("Denim Jacket", "Jacket", "Vintage", "DenimLab", 1999, "jacket-denim"),
    ("Pullover Hoodie", "Hoodie", "Sporty", "FlexFit", 1099, "hoodie-pullover"),
    ("Zip-Up Hoodie", "Hoodie", "Streetwear", "Northline", 1299, "hoodie-zip"),
    ("Cable Knit Sweater", "Sweater", "Vintage", "Heritage Loom", 1699, "sweater-cable"),
    ("Turtleneck Sweater", "Sweater", "Minimal", "Studio Form", 1499, "sweater-turtle"),
    ("Embroidered Kurta", "Kurta", "Traditional", "Heritage Loom", 1799, "kurta-embroidered"),
    ("Cotton Casual Kurta", "Kurta", "Casual", "Heritage Loom", 999, "kurta-cotton"),
    ("Banarasi Silk Saree", "Saree", "Traditional", "Heritage Loom", 4999, "saree-silk"),
    ("Chiffon Party Saree", "Saree", "Party", "Heritage Loom", 3299, "saree-chiffon"),
    ("Running Sneakers", "Sneakers", "Sporty", "FlexFit", 2499, "sneaker-running"),
    ("Retro Canvas Sneakers", "Sneakers", "Vintage", "FlexFit", 1799, "sneaker-canvas"),
    ("Formal Leather Shoes", "Shoes", "Formal", "Everett & Co.", 2999, "shoes-leather"),
]

COLORS = ["Black", "White", "Navy", "Beige", "Burgundy", "Olive"]


def make_placeholder_image(path: Path, rgb: tuple[int, int, int], label: str):
    img = Image.new("RGB", (400, 500), rgb)
    draw = ImageDraw.Draw(img)
    # subtle texture so embeddings differ slightly per "product photo"
    for i in range(0, 500, 40):
        shade = tuple(max(0, c - 12) for c in rgb)
        draw.line([(0, i), (400, i)], fill=shade, width=2)
    img.save(path, "JPEG", quality=85)


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("Products already seeded. Skipping. (Delete fashion.db to reseed.)")
        else:
            upload_dir = Path("uploads/products")
            upload_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            for name, category, style, brand, base_price, group in CATALOG:
                variant_colors = COLORS[:3] if category in ("Dress", "T-Shirt", "Shirt") else COLORS[:2]
                for color in variant_colors:
                    rgb = COLOR_RGB[color]
                    filename = f"{group}-{color.lower()}.jpg"
                    img_path = upload_dir / filename
                    make_placeholder_image(img_path, rgb, name)

                    vec = embedding_service.generate_embedding(str(img_path))
                    price = base_price + (hash(color) % 5) * 20
                    discount = price - 100 if count % 4 == 0 else None

                    product = Product(
                        name=f"{color} {name}",
                        description=f"A {style.lower()} {category.lower()} in {color.lower()}, perfect for everyday wear.",
                        brand=brand,
                        category=category,
                        subcategory=category,
                        style=style,
                        color=color,
                        pattern="Solid",
                        price=float(price),
                        discount_price=float(discount) if discount else None,
                        currency="INR",
                        image_url=f"/uploads/products/{filename}",
                        product_url="",
                        platform="Demo Store",
                        availability=True,
                        embedding_reference=embedding_service.to_string(vec),
                        group_key=group,
                    )
                    db.add(product)
                    count += 1
            db.commit()
            print(f"Seeded {count} demo products.")

        if not db.query(User).filter(User.email == "demo@fashionai.dev").first():
            user = User(name="Demo User", email="demo@fashionai.dev", password_hash=hash_password("demo1234"))
            db.add(user)
            db.flush()
            db.add(UserPreference(user_id=user.id, preferred_styles="Casual,Party", preferred_colors="Black,Navy", budget_min=0, budget_max=3000))
            db.commit()
            print("Created demo user: demo@fashionai.dev / demo1234")

        if not db.query(User).filter(User.email == "admin@fashionai.dev").first():
            admin = User(name="Demo Admin", email="admin@fashionai.dev", password_hash=hash_password("admin1234"), is_admin=True)
            db.add(admin)
            db.flush()
            db.add(UserPreference(user_id=admin.id))
            db.commit()
            print("Created demo admin: admin@fashionai.dev / admin1234")
    finally:
        db.close()


if __name__ == "__main__":
    run()
