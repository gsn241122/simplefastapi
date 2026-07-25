from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ModelBase(BaseModel):
    """Schema dasar untuk Model."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama model")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi model")


class ModelCreate(ModelBase):
    """Schema untuk membuat Model baru."""
    pass


class ModelUpdate(BaseModel):
    """Schema untuk mengupdate Model (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class ModelResponse(ModelBase):
    """Schema response untuk Model."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
