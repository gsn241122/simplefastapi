"""
SQLAlchemy model untuk Permission.

Permission merepresentasikan aksi spesifik yang dapat dilakukan pada resource,
contoh: "read:users", "write:products", "delete:orders".
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Permission(Base):
    """Model untuk tabel permissions."""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Format konvensi: "action:resource", contoh: "read:users", "write:products"
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    # Resource = entitas yang diakses (users, products, orders, dll)
    resource = Column(String(50), nullable=False, index=True)
    # Action = aksi yang diizinkan (read, write, delete, create, dll)
    action = Column(String(50), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Back-reference ke Role (relasi many-to-many didefinisikan di role/models.py)
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )

    # Composite index untuk pencarian cepat berdasarkan resource+action
    __table_args__ = (
        Index("ix_permissions_resource_action", "resource", "action"),
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name!r})>"
