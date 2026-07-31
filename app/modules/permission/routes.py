"""
HTTP routes untuk Permission management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.core.security import require_permission
from app.modules.permission import crud
from app.modules.permission.schemas import (
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=APIResponse, summary="List semua permission",
         dependencies=[Depends(require_permission("read:permissions"))])
def list_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, description="Cari berdasarkan nama/deskripsi"),
    resource: str | None = Query(None, description="Filter berdasarkan resource"),
    db: Session = Depends(get_db),
):
    items, total = crud.get_permissions(db, skip=skip, limit=limit, search=search, resource=resource)
    return StandardJSONResponse.success(
        data=[PermissionResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} permission.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{permission_id}", response_model=APIResponse, summary="Get permission by ID",
            dependencies=[Depends(require_permission("read:permissions"))])
def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
):
    item = crud.get_permission_by_id(db, permission_id)
    if not item:
        raise HTTPException(status_code=404, detail="Permission tidak ditemukan.")
    return StandardJSONResponse.success(
        data=PermissionResponse.model_validate(item),
        message="Permission berhasil ditemukan.",
    )


@router.post(
    "",
    response_model=APIResponse,
    status_code=201,
    summary="Create permission",
    dependencies=[Depends(require_permission("write:permissions"))],
)
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(get_db),
):
    # Cek duplikat nama
    if crud.get_permission_by_name(db, payload.name):
        raise HTTPException(
            status_code=400,
            detail=f"Permission dengan nama '{payload.name}' sudah ada.",
        )
    item = crud.create_permission(db, payload)
    return StandardJSONResponse.success(
        data=PermissionResponse.model_validate(item),
        message="Permission berhasil dibuat.",
    )


@router.put(
    "/{permission_id}",
    response_model=APIResponse,
    summary="Update permission",
    dependencies=[Depends(require_permission("write:permissions"))],
)
def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    db: Session = Depends(get_db),
):
    # Cek duplikat nama jika ada perubahan nama
    if payload.name and crud.get_permission_by_name(db, payload.name):
        existing = crud.get_permission_by_name(db, payload.name)
        if existing and existing.id != permission_id:
            raise HTTPException(
                status_code=400,
                detail=f"Permission dengan nama '{payload.name}' sudah ada.",
            )
    item = crud.update_permission(db, permission_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Permission tidak ditemukan.")
    return StandardJSONResponse.success(
        data=PermissionResponse.model_validate(item),
        message="Permission berhasil diupdate.",
    )


@router.delete(
    "/{permission_id}",
    response_model=APIResponse,
    summary="Delete permission",
    dependencies=[Depends(require_permission("delete:permissions"))],
)
def delete_permission(permission_id: int, db: Session = Depends(get_db)):
    success = crud.delete_permission(db, permission_id)
    if not success:
        raise HTTPException(status_code=404, detail="Permission tidak ditemukan.")
    return StandardJSONResponse.success(message="Permission berhasil dihapus.")


# Summary provider for aggregator
def get_summary(db, redis=None):
    """Return a small summary dict for the permission module."""
    try:
        _, total = crud.get_permissions(db, skip=0, limit=1)
    except Exception:
        total = 0
    return {"counts": {"permissions": total}, "meta": {"module": "permission"}}
