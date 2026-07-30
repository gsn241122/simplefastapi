"""
Service layer untuk Role: business logic + manajemen permission.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional, List

from app.modules.role.models import Role
from app.modules.role.schemas import RoleCreate, RoleUpdate
from app.modules.permission.models import Permission


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
    items = query.order_by(Role.id).offset(skip).limit(limit).all()
    return items, total


def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
    """Ambil satu role berdasarkan ID (ikut memuat permissions)."""
    return db.query(Role).filter(
        Role.id == role_id,
        Role.is_active == True,  # noqa: E712
    ).first()


def get_role_by_name(db: Session, name: str) -> Optional[Role]:
    """Ambil role berdasarkan nama (case-sensitive)."""
    return db.query(Role).filter(Role.name == name).first()


def create_role(db: Session, payload: RoleCreate) -> Role:
    """
    Buat role baru, dengan permission opsional.
    """
    role_data = payload.model_dump(exclude={"permission_ids"})
    db_item = Role(**role_data)

    if payload.permission_ids:
        perms = db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
        if len(perms) != len(payload.permission_ids):
            raise ValueError(
                f"Satu atau lebih permission_id tidak ditemukan: {payload.permission_ids}"
            )
        db_item.permissions = perms

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_role(
    db: Session,
    role_id: int,
    payload: RoleUpdate,
) -> Optional[Role]:
    """
    Update role. Jika `permission_ids` ada, ganti semua permission dengan
    daftar baru (replace, bukan append).
    """
    db_item = get_role_by_id(db, role_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True, exclude={"permission_ids"})

    for key, value in update_data.items():
        setattr(db_item, key, value)

    if payload.permission_ids is not None:
        perms = db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
        if len(perms) != len(payload.permission_ids):
            raise ValueError(
                f"Satu atau lebih permission_id tidak ditemukan: {payload.permission_ids}"
            )
        db_item.permissions = list(perms)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_role(db: Session, role_id: int) -> bool:
    """
    Soft-delete role. Mencegah penghapusan role default 'user' dan 'admin'.
    """
    db_item = db.query(Role).filter(Role.id == role_id).first()
    if not db_item:
        return False

    # Lindungi role default
    if db_item.name in ("user", "admin"):
        raise ValueError(
            f"Tidak dapat menghapus role default '{db_item.name}'."
        )

    db_item.is_active = False
    db.commit()
    return True


# ─── Permission Management per Role ─────────────────────────────────────────────

def assign_permissions_to_role(
    db: Session,
    role_id: int,
    permission_ids: List[int],
) -> Optional[Role]:
    """Replace semua permission role dengan daftar baru."""
    db_item = get_role_by_id(db, role_id)
    if not db_item:
        return None

    perms = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
    if len(perms) != len(permission_ids):
        raise ValueError(
            f"Satu atau lebih permission_id tidak ditemukan: {permission_ids}"
        )
    db_item.permissions = list(perms)
    db.commit()
    db.refresh(db_item)
    return db_item


def add_permission_to_role(
    db: Session,
    role_id: int,
    permission_id: int,
) -> Optional[Role]:
    """Tambahkan satu permission ke role (tidak menimpa)."""
    db_item = get_role_by_id(db, role_id)
    if not db_item:
        return None

    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise ValueError(f"Permission id={permission_id} tidak ditemukan")

    if perm not in db_item.permissions:
        db_item.permissions.append(perm)
        db.commit()
        db.refresh(db_item)
    return db_item


def remove_permission_from_role(
    db: Session,
    role_id: int,
    permission_id: int,
) -> Optional[Role]:
    """Hapus satu permission dari role."""
    db_item = get_role_by_id(db, role_id)
    if not db_item:
        return None

    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise ValueError(f"Permission id={permission_id} tidak ditemukan")

    if perm in db_item.permissions:
        db_item.permissions.remove(perm)
        db.commit()
        db.refresh(db_item)
    return db_item
