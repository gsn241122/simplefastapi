from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.film import service
from app.modules.film.schemas import (
    FilmCreate,
    FilmResponse,
    FilmUpdate,
)

from app.modules.auth.routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/films",
    tags=["Films"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=APIResponse, summary="List semua film")
def list_films(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    sort_by: str = Query("id", description="Kolom untuk sorting"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Urutan sorting"),
    db: Session = Depends(get_db),
):
    """Ambil daftar film dengan paginasi."""
    items, total = service.get_film_list(
        db, skip=skip, limit=limit, search=search, sort_by=sort_by, sort_order=sort_order
    )
    return StandardJSONResponse.success(
        data=[FilmResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} film.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get film by ID")
def get_film(id: int, db: Session = Depends(get_db)):
    """Ambil detail film berdasarkan ID."""
    item = service.get_film_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Film tidak ditemukan.")
    return StandardJSONResponse.success(
        data=FilmResponse.model_validate(item),
        message="Film berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create film")
def create_film(payload: FilmCreate, db: Session = Depends(get_db)):
    """Buat film baru."""
    try:
        item = service.create_film(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Film dengan data tersebut sudah ada.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal membuat film, silakan coba lagi.")
    return StandardJSONResponse.success(
        data=FilmResponse.model_validate(item),
        message="Film berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update film")
def update_film(id: int, payload: FilmUpdate, db: Session = Depends(get_db)):
    """Update film berdasarkan ID."""
    try:
        item = service.update_film(db, id, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Update menyebabkan konflik data.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal mengupdate film, silakan coba lagi.")
    if not item:
        raise HTTPException(status_code=404, detail="Film tidak ditemukan.")
    return StandardJSONResponse.success(
        data=FilmResponse.model_validate(item),
        message="Film berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete film")
def delete_film(id: int, db: Session = Depends(get_db)):
    """Soft-delete film berdasarkan ID."""
    success = service.delete_film(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Film tidak ditemukan.")
    return StandardJSONResponse.success(message="Film berhasil dihapus.")


# Summary provider for aggregator
def get_summary(db, _redis=None):
    """Return summary data for the film module."""
    try:
        _, total = service.get_film_list(
            db,
            skip=0,
            limit=1,
        )
    except SQLAlchemyError:
        logger.exception("Gagal mengambil summary film")
        total = 0

    return {
        "counts": {
            "films": total
        },
        "meta": {
            "module": "film"
        }
    }
