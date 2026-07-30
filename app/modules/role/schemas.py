"""
Pydantic schemas untuk Role dengan relasi ke Permission.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Forward declaration untuk Permission (diimpor di bawah untuk avoid circular)
class _PermissionBrief(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    """Schema dasar untuk Role."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama role")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi role")


class RoleCreate(RoleBase):
    """Schema untuk membuat Role baru."""

    permission_ids: Optional[List[int]] = Field(
        default=None,
        description="Daftar ID permission yang dimiliki role ini (opsional).",
        example=[1, 2, 3],
    )


class RoleUpdate(BaseModel):
    """Schema untuk mengupdate Role (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = Field(
        default=None,
        description="Ganti semua permission role dengan daftar ID ini.",
    )


class RoleResponse(RoleBase):
    """Schema response untuk Role dengan permissions."""

    id: int
    is_active: bool
    permissions: List[_PermissionBrief] = Field(
        default_factory=list,
        description="Daftar permission yang dimiliki role ini.",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_role_orm(cls, role) -> "RoleResponse":
        """Build RoleResponse dari ORM Role, sertakan permissions."""
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            is_active=role.is_active,
            permissions=[
                _PermissionBrief(
                    id=p.id,
                    name=p.name,
                    resource=p.resource,
                    action=p.action,
                )
                for p in role.permissions
            ],
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
