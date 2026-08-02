from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PaymentBase(BaseModel):
    """Schema dasar untuk Payment."""

    invoice_id: int = Field(..., description="ID Invoice terkait")
    payment_method: str = Field(..., description="Metode pembayaran")
    payment_date: datetime = Field(..., description="Tanggal pembayaran")
    amount: int = Field(..., description="Jumlah pembayaran")
    status: Optional[str] = Field("pending", description="Status pembayaran")


class PaymentCreate(PaymentBase):
    """Schema untuk membuat Payment baru."""
    pass


class PaymentUpdate(BaseModel):
    """Schema untuk mengupdate Payment (semua field opsional)."""

    invoice_id: Optional[int] = Field(None, description="ID Invoice terkait")
    payment_method: Optional[str] = Field(None, description="Metode pembayaran")
    payment_date: Optional[datetime] = Field(None, description="Tanggal pembayaran")
    amount: Optional[int] = Field(None, description="Jumlah pembayaran")
    status: Optional[str] = Field(None, description="Status pembayaran")


class PaymentResponse(PaymentBase):
    """Schema response untuk Payment."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
