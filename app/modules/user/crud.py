"""
CRUD operations untuk User, termasuk manajemen role RBAC.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.modules.user.models import User
from app.modules.role.models import Role
from app.modules.role import crud as role_crud


def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id, User.is_deleted == False).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username, User.is_deleted == False).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email, User.is_deleted == False).first()


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> tuple[list, int]:
    """Get paginated list of active users with optional search filter."""
    query = db.query(User).filter(User.is_deleted == False)  # noqa: E712
    if search:
        query = query.filter(
            User.username.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.full_name.ilike(f"%{search}%")
        )
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def _sync_legacy_role_field(db: Session, user: User) -> None:
    """
    Sinkronkan field legacy `User.role` (string) dengan relasi `User.roles`.

    Logikanya:
    - Jika user punya role 'admin' di relasi → field legacy = 'admin'
    - Selain itu → field legacy = 'user' (default)
    - Jika relasi kosong → field legacy = 'user'
    """
    legacy_value = "user"
    for role in user.roles:
        if role.name == "admin":
            legacy_value = "admin"
            break
    user.role = legacy_value


def create_user(db: Session, user_data: Dict[str, Any]) -> User:
    """
    Buat user baru. Mendukung RBAC via `role_ids`.

    Args:
        db: Database session.
        user_data: Dict berisi data user. Jika `role_ids` ada, user akan
                   di-link ke role-role tersebut. Field `role` (legacy string)
                   akan diabaikan dan di-sync otomatis dari relasi.

    Returns:
        User yang baru dibuat.
    """
    role_ids = user_data.pop("role_ids", None)

    # Hapus field 'role' dari data yang akan di-insert — akan di-sync nanti
    user_data.pop("role", None)

    db_user = User(**user_data)
    db.add(db_user)
    db.flush()  # agar dapat id tanpa commit

    # Assign role jika ada
    if role_ids:
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
        if len(roles) != len(role_ids):
            db.rollback()
            raise ValueError(f"Satu atau lebih role_id tidak ditemukan: {role_ids}")
        db_user.roles = roles

    # Default: assign role 'user' jika tidak ada role sama sekali
    if not db_user.roles:
        default_role = role_crud.get_role_by_name(db, "user")
        if default_role:
            db_user.roles = [default_role]

    _sync_legacy_role_field(db, db_user)

    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(
    db: Session,
    user_id: int,
    user_update_data: Dict[str, Any],
) -> Optional[User]:
    """
    Update user. Mendukung penggantian role via `role_ids`.

    Logika `role_ids`:
    - Jika ada di payload → ganti semua role user dengan daftar ini
    - Jika tidak ada di payload → biarkan role user tidak berubah
    """
    db_user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not db_user:
        return None

    # Handle role_ids terpisah
    role_ids = user_update_data.pop("role_ids", None)
    # Field 'role' legacy di-drop; akan di-sync otomatis dari relasi
    user_update_data.pop("role", None)

    # Update field biasa
    for key, value in user_update_data.items():
        setattr(db_user, key, value)

    # Update relasi role jika diminta
    if role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
        if len(roles) != len(role_ids):
            raise ValueError(f"Satu atau lebih role_id tidak ditemukan: {role_ids}")
        db_user.roles = roles

    # Re-sync field legacy
    _sync_legacy_role_field(db, db_user)

    db.commit()
    db.refresh(db_user)
    return db_user


def assign_roles_to_user(
    db: Session,
    user_id: int,
    role_ids: List[int],
) -> Optional[User]:
    """
    Assign satu atau lebih role ke user.

    Args:
        db: Database session.
        user_id: ID user.
        role_ids: Daftar ID role.

    Returns:
        User yang sudah di-update, atau None jika user tidak ditemukan.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    if len(roles) != len(role_ids):
        raise ValueError(f"Satu atau lebih role_id tidak ditemukan: {role_ids}")

    db_user.roles = list(roles)
    _sync_legacy_role_field(db, db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def add_role_to_user(
    db: Session,
    user_id: int,
    role_id: int,
) -> Optional[User]:
    """Tambahkan satu role ke user (tidak menimpa role yang sudah ada)."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    role = role_crud.get_role_by_id(db, role_id)
    if not role:
        raise ValueError(f"Role id={role_id} tidak ditemukan")

    if role not in db_user.roles:
        db_user.roles.append(role)
        _sync_legacy_role_field(db, db_user)
        db.commit()
        db.refresh(db_user)
    return db_user


def remove_role_from_user(
    db: Session,
    user_id: int,
    role_id: int,
) -> Optional[User]:
    """Hapus satu role dari user."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    role = role_crud.get_role_by_id(db, role_id)
    if not role:
        raise ValueError(f"Role id={role_id} tidak ditemukan")

    if role in db_user.roles:
        db_user.roles.remove(role)
        # Pastikan user tetap punya minimal 1 role
        if not db_user.roles:
            default_role = role_crud.get_role_by_name(db, "user")
            if default_role:
                db_user.roles.append(default_role)
        _sync_legacy_role_field(db, db_user)
        db.commit()
        db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int):
    db_user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if db_user:
        db_user.is_deleted = True
        db_user.deleted_at = datetime.now(timezone.utc)
        db.commit()
    return db_user
