from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.role import service
from app.modules.role.schemas import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua role")
def list_roles(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar role dengan paginasi."""
    items, total = service.get_role_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[RoleResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} role.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get role by ID")
def get_role(id: int, db: Session = Depends(get_db)):
    """Ambil detail role berdasarkan ID."""
    item = service.get_role_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.model_validate(item),
        message="Role berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create role")
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    """Buat role baru."""
    item = service.create_role(db, payload)
    return StandardJSONResponse.success(
        data=RoleResponse.model_validate(item),
        message="Role berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update role")
def update_role(id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    """Update role berdasarkan ID."""
    item = service.update_role(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(
        data=RoleResponse.model_validate(item),
        message="Role berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete role")
def delete_role(id: int, db: Session = Depends(get_db)):
    """Soft-delete role berdasarkan ID."""
    success = service.delete_role(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan.")
    return StandardJSONResponse.success(message="Role berhasil dihapus.")
