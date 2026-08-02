from __future__ import annotations

from sqlalchemy import Column, Boolean, DateTime, Integer, String, Index
from sqlalchemy.sql import func

from app.core.database import Base


class Customer(Base):
    """SQLAlchemy model untuk Customer."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_is_active_id", "is_active", "id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name={self.name!r}, is_active={self.is_active})>"
