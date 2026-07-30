"""
Pydantic schemas untuk Permission.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PermissionBase(BaseModel):
    """Schema dasar Permission."""

    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nama permission dengan format 'action:resource'",
        examples=["read:users", "write:products"],
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Deskripsi permission"
    )
    resource: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Resource yang diakses (users, products, orders, dll)",
        examples=["users"],
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Aksi yang diizinkan (read, write, delete, create, dll)",
        examples=["read"],
    )


class PermissionCreate(PermissionBase):
    """Schema untuk membuat permission baru."""
    pass


class PermissionUpdate(BaseModel):
    """Schema untuk update permission (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    resource: Optional[str] = Field(None, min_length=1, max_length=50)
    action: Optional[str] = Field(None, min_length=1, max_length=50)


class PermissionResponse(PermissionBase):
    """Schema untuk response permission."""

    id: int = Field(..., description="ID permission")
    created_at: datetime = Field(..., description="Waktu dibuat")
    updated_at: datetime = Field(..., description="Waktu terakhir diupdate")

    model_config = {"from_attributes": True}
