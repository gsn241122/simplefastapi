from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BookBase(BaseModel):
    """Schema dasar untuk Book."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama book")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi book")
    judul: Optional[str] = None
    penerbit: Optional[str] = None


class BookCreate(BookBase):
    """Schema untuk membuat Book baru."""
    pass


class BookUpdate(BaseModel):
    """Schema untuk mengupdate Book (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    judul: Optional[str] = None
    penerbit: Optional[str] = None

    is_active: Optional[bool] = None


class BookResponse(BookBase):
    """Schema response untuk Book."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
