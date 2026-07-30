"""
HTTP routes untuk User management dengan RBAC.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.core.security import (
    get_password_hash,
    require_permission,
    require_admin,
)
from app.core.email import send_email
from app.modules.user import crud, schemas
from app.modules.auth.routes import get_current_user
from app.modules.user.models import User

router = APIRouter(prefix="/users", tags=["User Management"], dependencies=[Depends(get_current_user)])


# ─── List & Detail ──────────────────────────────────────────────────────────────

@router.get("/", response_model=APIResponse, summary="List semua user")
def read_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, description="Search by username, email, or full name"),
    db: Session = Depends(get_db),
    # Hanya yang punya permission read:users boleh lihat daftar
    _current: User = Depends(require_permission("read:users")),
):
    items, total = crud.get_users(db, skip=skip, limit=limit, search=search)
    response_data = [schemas.UserResponse.from_user_orm(u) for u in items]
    return StandardJSONResponse.success(
        data=response_data,
        message="Users retrieved successfully",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/me/permissions", response_model=APIResponse, summary="List permission user saat ini")
def get_my_permissions(current_user: User = Depends(get_current_user)):
    """Kembalikan daftar permission user yang sedang login."""
    return StandardJSONResponse.success(
        data={
            "username": current_user.username,
            "roles": sorted(current_user.role_names),
            "permissions": sorted(current_user.permissions),
        },
        message="Permission user berhasil diambil.",
    )


# ─── Create ─────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register user baru (admin only)",
)
def create_user(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Hanya admin (atau yang punya write:users) yang boleh buat user baru
    _admin: User = Depends(require_permission("write:users")),
):
    if crud.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_data = user.model_dump()
    user_data["hashed_password"] = get_password_hash(user.password)
    user_data.pop("password", None)
    # `role` legacy di-drop (di-handle di crud.create_user)
    # `role_ids` di-handle oleh crud untuk relasi many-to-many

    try:
        created_user = crud.create_user(db=db, user_data=user_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    response_data = schemas.UserResponse.from_user_orm(created_user)

    # Welcome email
    subject = f"Welcome to {settings.APP_NAME}!"
    user_name = user.full_name or user.username
    body = f"""Hi {user_name},

Welcome to {settings.APP_NAME}! We're excited to have you on board.

Your account has been successfully created with the email: {user.email}

You can now log in and start using our services.

If you have any questions, please don't hesitate to reach out to our support team.

Best regards,
The {settings.APP_NAME} Team
"""
    background_tasks.add_task(send_email, subject=subject, recipients=user.email, body=body)

    return StandardJSONResponse.success(
        data=response_data, message="User created successfully"
    )


# ─── Detail / Update / Delete ───────────────────────────────────────────────────

@router.get("/{user_id}", response_model=APIResponse, summary="Get user by ID")
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ambil user by ID. User hanya boleh lihat profil sendiri kecuali
    punya permission `read:users`.
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    has_perm = current_user.has_permission("read:users")
    is_self = current_user.id == user_id
    if not (has_perm or is_self):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions.",
        )

    return StandardJSONResponse.success(
        data=schemas.UserResponse.from_user_orm(db_user),
        message="User retrieved successfully",
    )


@router.put("/{user_id}", response_model=APIResponse, summary="Update user")
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_self = current_user.id == user_id
    is_admin = current_user.has_role("admin")
    has_write_perm = current_user.has_permission("write:users")

    # Hanya admin / punya write:users, atau diri sendiri yang boleh update
    if not (is_admin or has_write_perm or is_self):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions.",
        )

    update_data = user_update.model_dump(exclude_unset=True)

    # Password handling
    if "password" in update_data and update_data["password"] is not None:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # Hanya admin yang boleh ubah role / is_active
    if ("role" in update_data or "role_ids" in update_data) and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles.",
        )
    if "is_active" in update_data and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user active status.",
        )

    try:
        db_user = crud.update_user(db, user_id=user_id, user_update_data=update_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return StandardJSONResponse.success(
        data=schemas.UserResponse.from_user_orm(db_user),
        message="User updated successfully",
    )


@router.delete(
    "/{user_id}",
    response_model=APIResponse,
    summary="Delete user (soft delete)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),  # hanya admin
):
    if user_id == _admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot delete their own account.",
        )
    db_user = crud.delete_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(message="User soft deleted successfully")


# ─── Role Assignment (RBAC) ─────────────────────────────────────────────────────

@router.post(
    "/{user_id}/roles",
    response_model=APIResponse,
    summary="Replace user's roles (admin only)",
)
def assign_user_roles(
    user_id: int,
    role_ids: list[int],
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Ganti semua role user dengan daftar ID baru.

    Body: `[1, 2, 3]`
    """
    try:
        updated = crud.assign_roles_to_user(db, user_id, role_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(
        data=schemas.UserResponse.from_user_orm(updated),
        message=f"Berhasil assign {len(role_ids)} role ke user.",
    )


@router.post(
    "/{user_id}/roles/{role_id}/add",
    response_model=APIResponse,
    summary="Add single role to user (admin only)",
)
def add_user_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Tambahkan satu role ke user (tidak menimpa)."""
    try:
        updated = crud.add_role_to_user(db, user_id, role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(
        data=schemas.UserResponse.from_user_orm(updated),
        message="Role berhasil ditambahkan.",
    )


@router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=APIResponse,
    summary="Remove role from user (admin only)",
)
def remove_user_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Hapus satu role dari user."""
    try:
        updated = crud.remove_role_from_user(db, user_id, role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(
        data=schemas.UserResponse.from_user_orm(updated),
        message="Role berhasil dihapus.",
    )
