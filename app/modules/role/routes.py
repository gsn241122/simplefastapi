"""
HTTP routes untuk Role management + permission assignment.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.core.security import require_permission
from app.modules.role import service
from app.modules.role.schemas import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"], dependencies=[Depends(get_current_user)])


# ─── Helper: konversi exception service menjadi HTTPException ──────────────────
def _handle_service_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ─── Role CRUD ──────────────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse, summary="List semua role")
def list_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar role dengan paginasi."""
    items, total = service.get_role_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[RoleResponse.from_role_orm(i) for i in items],
        message=f"Berhasil mengambil {len(items)} role.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get role by ID")
def get_role(id: int, db: Session = Depends(get_db)):
    """Ambil detail role + permissions berdasarkan ID."""
    item = service.get_role_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message="Role berhasil ditemukan.",
    )


@router.post(
    "",
    response_model=APIResponse,
    status_code=201,
    summary="Create role",
    dependencies=[Depends(require_permission("write:roles"))],
)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    """Buat role baru. Memerlukan permission `write:roles`."""
    try:
        item = service.create_role(db, payload)
    except ValueError as exc:
        raise _handle_service_error(exc)
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message="Role berhasil dibuat.",
    )


@router.put(
    "/{id}",
    response_model=APIResponse,
    summary="Update role",
    dependencies=[Depends(require_permission("write:roles"))],
)
def update_role(id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    """Update role berdasarkan ID. Memerlukan permission `write:roles`."""
    try:
        item = service.update_role(db, id, payload)
    except ValueError as exc:
        raise _handle_service_error(exc)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message="Role berhasil diupdate.",
    )


@router.delete(
    "/{id}",
    response_model=APIResponse,
    summary="Delete role",
    dependencies=[Depends(require_permission("delete:roles"))],
)
def delete_role(id: int, db: Session = Depends(get_db)):
    """Soft-delete role. Memerlukan permission `delete:roles`."""
    try:
        success = service.delete_role(db, id)
    except ValueError as exc:
        raise _handle_service_error(exc)
    if not success:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(message="Role berhasil dihapus.")


# ─── Permission Management per Role ─────────────────────────────────────────────

@router.post(
    "/{role_id}/permissions",
    response_model=APIResponse,
    summary="Assign permissions to role (replace)",
    dependencies=[Depends(require_permission("write:roles"))],
)
def assign_permissions(role_id: int, permission_ids: list[int], db: Session = Depends(get_db)):
    """
    Ganti semua permission role dengan daftar baru (replace, bukan append).

    Body: `[1, 2, 3]`
    """
    try:
        item = service.assign_permissions_to_role(db, role_id, permission_ids)
    except ValueError as exc:
        raise _handle_service_error(exc)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message=f"Berhasil assign {len(permission_ids)} permission ke role.",
    )


@router.post(
    "/{role_id}/permissions/{permission_id}/add",
    response_model=APIResponse,
    summary="Add single permission to role",
    dependencies=[Depends(require_permission("write:roles"))],
)
def add_permission(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    """Tambahkan satu permission ke role (tidak menimpa)."""
    try:
        item = service.add_permission_to_role(db, role_id, permission_id)
    except ValueError as exc:
        raise _handle_service_error(exc)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message="Permission berhasil ditambahkan.",
    )


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    response_model=APIResponse,
    summary="Remove permission from role",
    dependencies=[Depends(require_permission("write:roles"))],
)
def remove_permission(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    """Hapus satu permission dari role."""
    try:
        item = service.remove_permission_from_role(db, role_id, permission_id)
    except ValueError as exc:
        raise _handle_service_error(exc)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.from_role_orm(item),
        message="Permission berhasil dihapus.",
    )
