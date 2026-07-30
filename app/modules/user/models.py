"""
SQLAlchemy model untuk User dengan relasi many-to-many ke Role.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base
# Import Role agar relasi ter-resolve & tabel pivot terdaftar di Base.metadata
from app.modules.role.models import Role  # noqa: F401


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    # Field legacy: disimpan sebagai string "user"/"admin" untuk backward-compat.
    # Disinkronkan otomatis dengan role pertama user di tabel roles.
    role = Column(String, default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relasi many-to-many ke Role (tabel pivot didefinisikan di role/models.py)
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )

    @property
    def permissions(self) -> set[str]:
        """
        Kumpulkan semua nama permission dari semua role user.

        Returns:
            Set berisi nama-nama permission (contoh: {"read:users", "write:products"}).
        """
        perms: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.name)
        return perms

    @property
    def role_names(self) -> set[str]:
        """Kumpulkan nama role user."""
        return {role.name for role in self.roles}

    def has_role(self, role_name: str) -> bool:
        """Cek apakah user memiliki role tertentu."""
        return role_name in self.role_names

    def has_permission(self, permission_name: str) -> bool:
        """Cek apakah user memiliki permission tertentu (melalui role-nya)."""
        return permission_name in self.permissions
