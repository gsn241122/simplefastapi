from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProviderBase(BaseModel):
    """Schema dasar untuk Provider."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama provider")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi provider")


class ProviderCreate(ProviderBase):
    """Schema untuk membuat Provider baru."""
    pass


class ProviderUpdate(BaseModel):
    """Schema untuk mengupdate Provider (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class ProviderResponse(ProviderBase):
    """Schema response untuk Provider."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
