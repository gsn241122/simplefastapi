"""
CRUD operations untuk Permission.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.permission.models import Permission
from app.modules.permission.schemas import PermissionCreate, PermissionUpdate


def get_permission_by_id(db: Session, permission_id: int) -> Optional[Permission]:
    """Ambil satu permission berdasarkan ID."""
    return db.query(Permission).filter(Permission.id == permission_id).first()


def get_permission_by_name(db: Session, name: str) -> Optional[Permission]:
    """Ambil permission berdasarkan nama (case-insensitive)."""
    return db.query(Permission).filter(Permission.name == name).first()


def get_permissions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    resource: Optional[str] = None,
) -> tuple[list[Permission], int]:
    """
    Ambil daftar permission dengan paginasi dan filter opsional.

    Returns:
        Tuple (list Permission, total count).
    """
    query = db.query(Permission)

    if search:
        query = query.filter(
            Permission.name.ilike(f"%{search}%")
            | Permission.description.ilike(f"%{search}%")
        )

    if resource:
        query = query.filter(Permission.resource == resource)

    total = query.count()
    items = query.order_by(Permission.resource, Permission.action).offset(skip).limit(limit).all()
    return items, total


def create_permission(db: Session, payload: PermissionCreate) -> Permission:
    """Buat permission baru."""
    db_item = Permission(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_permission(
    db: Session,
    permission_id: int,
    payload: PermissionUpdate,
) -> Optional[Permission]:
    """Update permission berdasarkan ID."""
    db_item = get_permission_by_id(db, permission_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_permission(db: Session, permission_id: int) -> bool:
    """Hapus permission secara permanen."""
    db_item = get_permission_by_id(db, permission_id)
    if not db_item:
        return False
    db.delete(db_item)
    db.commit()
    return True
