from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


# --- Token Schemas ---

class Token(BaseModel):
    """Schema untuk JWT access token."""

    access_token: str = Field(..., description="JWT access token", example="eyJhbGci...")
    token_type: str = Field(..., description="Tipe token", example="bearer")


class TokenData(BaseModel):
    """Schema untuk data yang ada di dalam payload JWT."""

    username: Optional[str] = None


# --- User Schemas ---

class UserBase(BaseModel):
    """Field dasar yang digunakan oleh semua user schema."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username unik pengguna",
        example="john_doe",
    )
    email: EmailStr = Field(
        ...,
        description="Alamat email unik pengguna",
        example="john@example.com",
    )
    full_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Nama lengkap pengguna",
        example="John Doe",
    )
    is_active: bool = Field(
        default=True,
        description="Status aktif pengguna",
        example=True,
    )


class UserCreate(UserBase):
    """Schema untuk membuat user baru."""

    password: str = Field(
        ...,
        min_length=8,
        description=(
            "Password pengguna. Minimal 8 karakter, harus mengandung "
            "huruf kapital, huruf kecil, angka, dan karakter spesial."
        ),
        example="S3cur3P@ss!",
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Pastikan username hanya mengandung huruf, angka, dan underscore."""
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username hanya boleh mengandung huruf, angka, dan underscore (_).")
        return v


class UserUpdate(BaseModel):
    """Schema untuk memperbarui data user (semua field opsional)."""

    username: Optional[str] = Field(
        None, min_length=3, max_length=50, example="new_username"
    )
    email: Optional[EmailStr] = Field(
        None, example="newemail@example.com"
    )
    full_name: Optional[str] = Field(
        None, max_length=100, example="New Full Name"
    )
    is_active: Optional[bool] = Field(None, example=True)
    password: Optional[str] = Field(
        None,
        min_length=8,
        description="Password baru. Kosongkan jika tidak ingin diubah.",
        example="NewS3cur3P@ss!",
    )


class UserResponse(UserBase):
    """Schema untuk response data user (tidak termasuk password)."""

    id: int = Field(..., description="ID unik pengguna", example=1)
    created_at: Optional[datetime] = Field(None, description="Waktu pembuatan akun")
    updated_at: Optional[datetime] = Field(None, description="Waktu terakhir diperbarui")
    is_deleted: bool = Field(False, description="Apakah akun sudah dihapus (soft delete)")
    deleted_at: Optional[datetime] = Field(None, description="Waktu penghapusan akun")

    model_config = {"from_attributes": True}
