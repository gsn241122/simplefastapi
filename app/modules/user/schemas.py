"""
Pydantic schemas untuk User dengan dukungan RBAC.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# --- Forward references ---
class _PermissionBrief(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    model_config = {"from_attributes": True}


class _RoleBrief(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    model_config = {"from_attributes": True}


class _UserBrief(BaseModel):
    id: int
    username: str
    model_config = {"from_attributes": True}



# --- Token Schemas ---

class Token(BaseModel):
    """Schema untuk JWT access token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Tipe token")


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
    role: Optional[str] = Field(
        default="user",
        description="Role legacy (string). Disinkronkan ke tabel roles.",
        example="user",
    )
    role_ids: Optional[List[int]] = Field(
        default=None,
        description="ID role dari tabel roles (RBAC). Admin akan pakai ini.",
        example=[2],
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Pastikan username hanya mengandung huruf, angka, dan underscore."""
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username hanya boleh mengandung huruf, angka, dan underscore (_).")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validasi role legacy hanya boleh 'user' atau 'admin'."""
        if v is not None and v not in ["user", "admin"]:
            raise ValueError("Role hanya boleh 'user' atau 'admin'.")
        return v


class UserUpdate(BaseModel):
    """Schema untuk memperbarui data user (semua field opsional)."""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(
        None,
        min_length=8,
        description="Password baru. Kosongkan jika tidak ingin diubah.",
    )
    role: Optional[str] = Field(
        None,
        description="Role legacy (string). Disinkronkan ke tabel roles.",
        example="admin",
    )
    role_ids: Optional[List[int]] = Field(
        default=None,
        description="Ganti semua role user dengan daftar ID ini (RBAC).",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ["user", "admin"]:
            raise ValueError("Role hanya boleh 'user' atau 'admin'.")
        return v


class UserResponse(UserBase):
    """Schema untuk response data user (tidak termasuk password)."""

    id: int = Field(..., description="ID unik pengguna", example=1)
    # Role legacy (string) untuk backward compat
    role: str = Field(default="user", description="Role legacy (string)", example="user")
    # Role RBAC (relasi many-to-many)
    roles: List[_RoleBrief] = Field(
        default_factory=list,
        description="Daftar role RBAC user (relasi many-to-many).",
    )
    # Permission yang di-resolve dari role
    permissions: List[str] = Field(
        default_factory=list,
        description="Daftar nama permission (di-resolve otomatis dari role).",
    )
    created_at: Optional[datetime] = Field(None, description="Waktu pembuatan akun")
    updated_at: Optional[datetime] = Field(None, description="Waktu terakhir diperbarui")
    is_deleted: bool = Field(False, description="Apakah akun sudah dihapus (soft delete)")
    deleted_at: Optional[datetime] = Field(None, description="Waktu penghapusan akun")

    model_config = {"from_attributes": True}

    @classmethod
    def from_user_orm(cls, user) -> "UserResponse":
        """
        Helper untuk membuat UserResponse dari ORM User.
        Memetakan relasi `roles` & `permissions` secara eksplisit.
        """
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            role=user.role,
            roles=[
                _RoleBrief(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    is_active=r.is_active,
                )
                for r in user.roles
            ],
            permissions=sorted(user.permissions),
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_deleted=user.is_deleted,
            deleted_at=user.deleted_at,
        )

# Rebuild Pydantic models setelah forward references di-update
UserResponse.model_rebuild() # noqa: F401

