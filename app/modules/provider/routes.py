from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.provider import service
from app.modules.provider.schemas import (
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/providers", tags=["Providers"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua provider")
def list_providers(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar provider dengan paginasi."""
    items, total = service.get_provider_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[ProviderResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} provider.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get provider by ID")
def get_provider(id: int, db: Session = Depends(get_db)):
    """Ambil detail provider berdasarkan ID."""
    item = service.get_provider_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Provider tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ProviderResponse.model_validate(item),
        message="Provider berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create provider")
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    """Buat provider baru."""
    item = service.create_provider(db, payload)
    return StandardJSONResponse.success(
        data=ProviderResponse.model_validate(item),
        message="Provider berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update provider")
def update_provider(id: int, payload: ProviderUpdate, db: Session = Depends(get_db)):
    """Update provider berdasarkan ID."""
    item = service.update_provider(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Provider tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ProviderResponse.model_validate(item),
        message="Provider berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete provider")
def delete_provider(id: int, db: Session = Depends(get_db)):
    """Soft-delete provider berdasarkan ID."""
    success = service.delete_provider(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider tidak ditemukan.")
    return StandardJSONResponse.success(message="Provider berhasil dihapus.")
