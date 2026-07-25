from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RoleBase(BaseModel):
    """Schema dasar untuk Role."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama role")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi role")


class RoleCreate(RoleBase):
    """Schema untuk membuat Role baru."""
    pass


class RoleUpdate(BaseModel):
    """Schema untuk mengupdate Role (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class RoleResponse(RoleBase):
    """Schema response untuk Role."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
