from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="favorites")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    image_path: Mapped[str] = mapped_column(String(500))
    detected_category: Mapped[str] = mapped_column(String(60), default="")
    detected_style: Mapped[str] = mapped_column(String(60), default="")
    detected_color: Mapped[str] = mapped_column(String(60), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="searches")
    results: Mapped[list["SearchResult"]] = relationship(back_populates="search", cascade="all, delete-orphan")


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("search_history.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    similarity_score: Mapped[float] = mapped_column(Float, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    rank: Mapped[int] = mapped_column(Integer, default=0)

    search: Mapped["SearchHistory"] = relationship(back_populates="results")


class Recommendation(Base):
    """Persisted recommendation breakdown, so scores/explanations survive page reloads."""
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("search_history.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    mode: Mapped[str] = mapped_column(String(30), default="best_match")
    visual_score: Mapped[float] = mapped_column(Float, default=0)
    category_score: Mapped[float] = mapped_column(Float, default=0)
    color_score: Mapped[float] = mapped_column(Float, default=0)
    style_score: Mapped[float] = mapped_column(Float, default=0)
    pattern_score: Mapped[float] = mapped_column(Float, default=0)
    budget_score: Mapped[float] = mapped_column(Float, default=0)
    preference_score: Mapped[float] = mapped_column(Float, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    reasons: Mapped[str] = mapped_column(Text, default="")  # JSON-encoded list of strings
