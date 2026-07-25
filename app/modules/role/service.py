from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.role.models import Role
from app.modules.role.schemas import RoleCreate, RoleUpdate


def get_role_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Role], int]:
    """
    Ambil daftar role dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Role, total count).
    """
    query = db.query(Role).filter(Role.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Role.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
    """Ambil satu role berdasarkan ID."""
    return db.query(Role).filter(
        Role.id == role_id,
        Role.is_active == True,  # noqa: E712
    ).first()


def create_role(db: Session, payload: RoleCreate) -> Role:
    """Buat role baru."""
    db_item = Role(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_role(
    db: Session,
    role_id: int,
    payload: RoleUpdate,
) -> Optional[Role]:
    """Update role berdasarkan ID."""
    db_item = get_role_by_id(db, role_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_role(db: Session, role_id: int) -> bool:
    """Soft-delete role berdasarkan ID."""
    db_item = db.query(Role).filter(Role.id == role_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
