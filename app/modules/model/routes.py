from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.model import service
from app.modules.model.schemas import (
    ModelCreate,
    ModelResponse,
    ModelUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/models", tags=["Models"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua model")
def list_models(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar model dengan paginasi."""
    items, total = service.get_model_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[ModelResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} model.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get model by ID")
def get_model(id: int, db: Session = Depends(get_db)):
    """Ambil detail model berdasarkan ID."""
    item = service.get_model_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Model tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ModelResponse.model_validate(item),
        message="Model berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create model")
def create_model(payload: ModelCreate, db: Session = Depends(get_db)):
    """Buat model baru."""
    item = service.create_model(db, payload)
    return StandardJSONResponse.success(
        data=ModelResponse.model_validate(item),
        message="Model berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update model")
def update_model(id: int, payload: ModelUpdate, db: Session = Depends(get_db)):
    """Update model berdasarkan ID."""
    item = service.update_model(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Model tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ModelResponse.model_validate(item),
        message="Model berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete model")
def delete_model(id: int, db: Session = Depends(get_db)):
    """Soft-delete model berdasarkan ID."""
    success = service.delete_model(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Model tidak ditemukan.")
    return StandardJSONResponse.success(message="Model berhasil dihapus.")
