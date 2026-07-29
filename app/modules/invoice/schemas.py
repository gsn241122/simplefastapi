from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class InvoiceBase(BaseModel):
    """Schema dasar untuk Invoice."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama invoice")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi invoice")
    invoice_type: str = Field(default="invoice", max_length=50, description="Tipe invoice (invoice, receipt, dll.)")
    amount: int = Field(0, ge=0, description="Jumlah pokok tagihan")
    tax_amount: int = Field(0, ge=0, description="Jumlah pajak")
    total_amount: int = Field(0, ge=0, description="Total tagihan (amount + tax_amount)")
    is_paid: bool = Field(default=False, description="Status pembayaran")
    due_date: Optional[datetime] = Field(None, description="Tanggal jatuh tempo")


class InvoiceCreate(InvoiceBase):
    """Schema untuk membuat Invoice baru."""
    pass


class InvoiceUpdate(BaseModel):
    """Schema untuk mengupdate Invoice (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    invoice_type: Optional[str] = Field(None, max_length=50)
    amount: Optional[int] = Field(None, ge=0)
    tax_amount: Optional[int] = Field(None, ge=0)
    total_amount: Optional[int] = Field(None, ge=0)
    is_paid: Optional[bool] = None
    due_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class InvoiceResponse(InvoiceBase):
    """Schema response untuk Invoice."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
