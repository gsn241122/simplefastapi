from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class OrderBase(BaseModel):
    """Schema dasar untuk Order."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama order")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi order")
    amount: int = Field(0, ge=0, description="Jumlah pokok order (dalam satuan terkecil, misal sen/rupiah)")
    tax_amount: int = Field(0, ge=0, description="Jumlah pajak")
    total_amount: int = Field(0, ge=0, description="Total keseluruhan (amount + tax_amount)")


class OrderCreate(OrderBase):
    """Schema untuk membuat Order baru."""

    @model_validator(mode="after")
    def compute_total(self) -> "OrderCreate":
        """Auto-hitung total_amount jika tidak diisi secara eksplisit."""
        if self.total_amount == 0 and (self.amount > 0 or self.tax_amount > 0):
            self.total_amount = self.amount + self.tax_amount
        return self


class OrderUpdate(BaseModel):
    """Schema untuk mengupdate Order (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    amount: Optional[int] = Field(None, ge=0)
    tax_amount: Optional[int] = Field(None, ge=0)
    total_amount: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class OrderResponse(OrderBase):
    """Schema response untuk Order."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
