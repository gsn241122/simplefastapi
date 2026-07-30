from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime
from datetime import datetime, timezone
from app.core.database import Base


class Product(Base):
    """Model SQLAlchemy untuk tabel products."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    image_url = Column(String, nullable=True)  # URL or path to the product image

    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} price={self.price}>"
