from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Payment(Base):
    """SQLAlchemy model untuk Payment."""

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    payment_method = Column(String(50), nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP", nullable=False)

    # Relationships
    invoice = relationship("Invoice", backref="payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, invoice_id={self.invoice_id}, payment_method='{self.payment_method}')>"
