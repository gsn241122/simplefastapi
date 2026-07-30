from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Session
from app.modules.role.models import Role
from app.modules.permission.models import Permission
from app.modules.role.schemas import RoleCreate, RoleUpdate


def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
    """Mengambil daftar roles."""
    return db.query(Role).offset(skip).limit(limit).all()


def get_role(db: Session, role_id: int) -> Optional[Role]:
    """Mengambil satu role berdasarkan ID."""
    return db.query(Role).filter(Role.id == role_id).first()


def get_role_by_name(db: Session, name: str) -> Optional[Role]:
    """Mengambil satu role berdasarkan nama."""
    return db.query(Role).filter(Role.name == name).first()


def create_role(db: Session, payload: RoleCreate) -> Role:
    """Membuat role baru dengan permissions."""
    permission_ids = payload.permission_ids or []
    permissions = []
    if permission_ids:
        permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()

    db_role = Role(
        name=payload.name,
        description=payload.description,
        permissions=permissions,
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


def update_role(db: Session, db_role: Role, payload: RoleUpdate) -> Role:
    """Mengupdate role dan permission-nya."""
    if payload.name is not None:
        db_role.name = payload.name
    if payload.description is not None:
        db_role.description = payload.description
    if payload.is_active is not None:
        db_role.is_active = payload.is_active

    if payload.permission_ids is not None:
        new_permissions = db.query(Permission).filter(
            Permission.id.in_(payload.permission_ids)
        ).all()
        db_role.permissions = new_permissions

    db.commit()
    db.refresh(db_role)
    return db_role


def delete_role(db: Session, role_id: int) -> bool:
    """Menghapus role."""
    db_role = get_role(db, role_id)
    if db_role:
        db.delete(db_role)
        db.commit()
        return True
    return False
