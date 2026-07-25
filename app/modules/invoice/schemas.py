from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class InvoiceBase(BaseModel):
    """Schema dasar untuk Invoice."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama invoice")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi invoice")


class InvoiceCreate(InvoiceBase):
    """Schema untuk membuat Invoice baru."""
    pass


class InvoiceUpdate(BaseModel):
    """Schema untuk mengupdate Invoice (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class InvoiceResponse(InvoiceBase):
    """Schema response untuk Invoice."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
