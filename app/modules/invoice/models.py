from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class Invoice(Base):
    """SQLAlchemy model untuk Invoice."""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    amount = Column(Integer, nullable=False, default=0)
    is_paid = Column(Boolean, default=False, nullable=False)
    invoice_type = Column(String(50), nullable=False, default="invoice")
    due_date = Column(DateTime(timezone=True), nullable=True)
    tax_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, name={self.name!r})>"
