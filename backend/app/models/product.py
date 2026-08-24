from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(60), index=True)
    subcategory: Mapped[str] = mapped_column(String(60), default="")
    style: Mapped[str] = mapped_column(String(60), default="")
    color: Mapped[str] = mapped_column(String(60), default="")
    pattern: Mapped[str] = mapped_column(String(60), default="Solid")
    price: Mapped[float] = mapped_column(Float, default=0)
    discount_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    product_url: Mapped[str] = mapped_column(String(500), default="")
    platform: Mapped[str] = mapped_column(String(120), default="Demo Store")
    availability: Mapped[bool] = mapped_column(Boolean, default=True)
    # embedding stored as comma-separated floats (see services/embedding.py)
    embedding_reference: Mapped[str] = mapped_column(Text, default="")
    group_key: Mapped[str] = mapped_column(String(120), default="")  # groups color variants of "same" product
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    """Size/stock variant of a product (kept separate from color-variant grouping)."""
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str] = mapped_column(String(20), default="M")
    stock: Mapped[int] = mapped_column(Integer, default=10)

    product: Mapped["Product"] = relationship(back_populates="variants")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
