from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class OrderItemBase(BaseModel):
    product_id: int = Field(..., description="ID Produk yang dibeli")
    quantity: int = Field(1, ge=1, description="Jumlah pembelian")


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(OrderItemBase):
    id: int
    price: Decimal

    model_config = {"from_attributes": True}


class OrderBase(BaseModel):
    """Schema dasar untuk Order."""
    name: str = Field(..., min_length=1, max_length=255, description="Nama/Judul order")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi order")
    status: Optional[str] = Field("pending", description="Status order: pending, processing, completed, cancelled")
    amount: int = Field(0, ge=0, description="Jumlah pokok order")
    tax_amount: int = Field(0, ge=0, description="Jumlah pajak")
    total_amount: int = Field(0, ge=0, description="Total keseluruhan")


class OrderCreate(OrderBase):
    """Schema untuk membuat Order baru beserta item produknya."""
    items: List[OrderItemCreate] = Field(..., description="Daftar item produk yang dipesan")

    @model_validator(mode="after")
    def compute_total(self) -> "OrderCreate":
        if self.total_amount == 0 and (self.amount > 0 or self.tax_amount > 0):
            self.total_amount = self.amount + self.tax_amount
        return self


class OrderUpdate(BaseModel):
    """Schema untuk mengupdate Order."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, max_length=50)
    amount: Optional[int] = Field(None, ge=0)
    tax_amount: Optional[int] = Field(None, ge=0)
    total_amount: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class OrderResponse(OrderBase):
    """Schema response untuk Order."""
    id: int
    user_id: Optional[int] = None
    is_active: bool
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
