"""
SQLAlchemy model untuk Role dengan relasi many-to-many ke User dan Permission.
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Table,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ─── Association Tables ──────────────────────────────────────────────────────────
# Many-to-many: User <-> Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: Role <-> Permission
# Didefinisikan di sini (bukan di permission/models.py) untuk menghindari
# circular import. SQLAlchemy tetap mendaftarkannya ke Base.metadata
# yang sama sehingga migrasi akan menemukannya.
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    """Model untuk tabel roles dengan relasi ke User & Permission."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relasi many-to-many ke User
    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )

    # Relasi many-to-many ke Permission
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name!r})>"
