from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OrderBase(BaseModel):
    """Schema dasar untuk Order."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama order")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi order")


class OrderCreate(OrderBase):
    """Schema untuk membuat Order baru."""
    pass


class OrderUpdate(BaseModel):
    """Schema untuk mengupdate Order (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class OrderResponse(OrderBase):
    """Schema response untuk Order."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
