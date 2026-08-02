from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


def _strip_or_none(v: Optional[str]) -> Optional[str]:
    """Strip whitespace; convert empty/whitespace-only strings to None."""
    if v is None:
        return v
    v = v.strip()
    return v or None


class CustomerBase(BaseModel):
    """Schema dasar untuk Customer."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama customer")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi customer")
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=255)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name tidak boleh kosong atau hanya berisi spasi")
        return v

    @field_validator("description", "email", "phone", "address", "city")
    @classmethod
    def strip_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class CustomerCreate(CustomerBase):
    """Schema untuk membuat Customer baru."""
    pass


class CustomerUpdate(BaseModel):
    """Schema untuk mengupdate Customer (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=255)

    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name tidak boleh kosong atau hanya berisi spasi")
        return v

    @field_validator("description", "email", "phone", "address", "city")
    @classmethod
    def strip_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class CustomerResponse(CustomerBase):
    """Schema response untuk Customer."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
