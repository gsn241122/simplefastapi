"""
Seeder default untuk roles, permissions, dan user admin.
Dipanggil saat aplikasi startup.
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.role.models import Role
from app.modules.permission.models import Permission
from app.modules.user.models import User
from app.modules.role import crud as role_crud
from app.modules.permission import crud as perm_crud
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


# ─── Default Permissions ────────────────────────────────────────────────────────
# Format: "action:resource" — atur berdasarkan resource yang ada.
DEFAULT_PERMISSIONS: list[dict] = [
    # Users
    {"name": "read:users", "resource": "users", "action": "read",
     "description": "Melihat daftar & detail user"},
    {"name": "write:users", "resource": "users", "action": "write",
     "description": "Membuat & mengupdate user"},
    {"name": "delete:users", "resource": "users", "action": "delete",
     "description": "Menghapus user"},

    # Roles
    {"name": "read:roles", "resource": "roles", "action": "read",
     "description": "Melihat daftar & detail role"},
    {"name": "write:roles", "resource": "roles", "action": "write",
     "description": "Membuat & mengupdate role"},
    {"name": "delete:roles", "resource": "roles", "action": "delete",
     "description": "Menghapus role"},

    # Permissions
    {"name": "read:permissions", "resource": "permissions", "action": "read",
     "description": "Melihat daftar & detail permission"},
    {"name": "write:permissions", "resource": "permissions", "action": "write",
     "description": "Membuat & mengupdate permission"},
    {"name": "delete:permissions", "resource": "permissions", "action": "delete",
     "description": "Menghapus permission"},

    # Products (resource contoh)
    {"name": "read:products", "resource": "products", "action": "read",
     "description": "Melihat produk"},
    {"name": "write:products", "resource": "products", "action": "write",
     "description": "Membuat & update produk"},
    {"name": "delete:products", "resource": "products", "action": "delete",
     "description": "Menghapus produk"},

    # Orders (resource contoh)
    {"name": "read:orders", "resource": "orders", "action": "read",
     "description": "Melihat order"},
    {"name": "write:orders", "resource": "orders", "action": "write",
     "description": "Membuat & update order"},
    {"name": "delete:orders", "resource": "orders", "action": "delete",
     "description": "Menghapus order"},
]


# ─── Default Roles + permission mapping ─────────────────────────────────────────
# admin dapat SEMUA permission; user hanya read:products & read:orders.
DEFAULT_ROLES: list[dict] = [
    {
        "name": "admin",
        "description": "Administrator dengan akses penuh ke seluruh sistem",
        "is_active": True,
        "permissions": "all",  # placeholder — akan diisi semua
    },
    {
        "name": "user",
        "description": "User biasa dengan akses terbatas",
        "is_active": True,
        "permissions": ["read:products", "read:orders"],
    },
    {
        "name": "moderator",
        "description": "Moderator yang dapat mengelola produk & order",
        "is_active": True,
        "permissions": [
            "read:products", "write:products",
            "read:orders", "write:orders",
            "read:users",
        ],
    },
]


def seed_permissions(db: Session) -> dict[str, Permission]:
    """
    Sinkronkan tabel permissions dengan DEFAULT_PERMISSIONS.
    - Buat permission baru jika belum ada.
    - Update permission existing (name, description) jika ada perubahan.
    Returns:
        Dict mapping name -> Permission.
    """
    result: dict[str, Permission] = {}

    for spec in DEFAULT_PERMISSIONS:
        existing = perm_crud.get_permission_by_name(db, spec["name"])
        if existing:
            # Update field yang mungkin berubah
            for key, value in spec.items():
                if getattr(existing, key) != value:
                    setattr(existing, key, value)
            result[spec["name"]] = existing
        else:
            from app.modules.permission.schemas import PermissionCreate
            payload = PermissionCreate(**spec)
            result[spec["name"]] = perm_crud.create_permission(db, payload)

    db.commit()
    logger.info("✅ Seeded %d permissions", len(result))
    return result


def seed_roles(db: Session, permissions_map: dict[str, Permission]) -> dict[str, Role]:
    """
    Sinkronkan tabel roles dengan DEFAULT_ROLES.
    Returns:
        Dict mapping name -> Role.
    """
    result: dict[str, Role] = {}

    for spec in DEFAULT_ROLES:
        role = role_crud.get_role_by_name(db, spec["name"])
        if not role:
            role = Role(
                name=spec["name"],
                description=spec["description"],
                is_active=spec["is_active"],
            )
            db.add(role)
            db.flush()
            logger.info("Created role: %s", spec["name"])
        else:
            # Update description/is_active jika berubah
            if role.description != spec["description"]:
                role.description = spec["description"]
            if role.is_active != spec["is_active"]:
                role.is_active = spec["is_active"]

        # Set permissions
        if spec["permissions"] == "all":
            # admin: semua permission
            role.permissions = list(permissions_map.values())
        else:
            role.permissions = [permissions_map[p_name] for p_name in spec["permissions"] if p_name in permissions_map]

        result[spec["name"]] = role

    db.commit()
    logger.info("✅ Seeded %d roles", len(result))
    return result


def seed_admin_user(db: Session, roles_map: dict[str, Role]) -> None:
    """
    Pastikan ada user admin default. Buat jika belum ada.
    Default credentials: admin / admin
    """
    admin_user = db.query(User).filter(User.username == "admin").first()
    if admin_user:
        # Pastikan admin punya role admin
        if not admin_user.has_role("admin"):
            admin_user.roles = [roles_map["admin"]]
            admin_user.role = "admin"
            db.commit()
            logger.info("Linked existing admin user to admin role")
        return

    admin_user = User(
        username="admin",
        email="admin@example.com",
        full_name="Administrator",
        hashed_password=get_password_hash("admin"),
        role="admin",
        is_active=True,
    )
    admin_user.roles = [roles_map["admin"]]
    db.add(admin_user)
    db.commit()
    logger.info("✅ Created default admin user (username=admin, password=admin)")


def seed_demo_user(db: Session, roles_map: dict[str, Role]) -> None:
    """Buat user demo (user biasa) untuk testing."""
    if db.query(User).filter(User.username == "demo").first():
        return

    demo = User(
        username="demo",
        email="demo@example.com",
        full_name="Demo User",
        hashed_password=get_password_hash("Demo@1234"),
        role="user",
        is_active=True,
    )
    demo.roles = [roles_map["user"]]
    db.add(demo)
    db.commit()
    logger.info("✅ Created demo user (username=demo, password=Demo@1234)")


def run_seed() -> None:
    """Entry point untuk menjalankan semua seeding."""
    db = SessionLocal()
    try:
        logger.info("🌱 Seeding RBAC data...")
        perms_map = seed_permissions(db)
        roles_map = seed_roles(db, perms_map)
        seed_admin_user(db, roles_map)
        seed_demo_user(db, roles_map)
        logger.info("🌱 Seeding selesai.")
    except Exception as exc:
        logger.error("❌ Seeding gagal: %s", exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Bisa dijalankan manual: python -m app.core.seed
    run_seed()
