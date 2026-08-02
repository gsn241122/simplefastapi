from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.book import service
from app.modules.book.schemas import (
    BookCreate,
    BookResponse,
    BookUpdate,
)

from app.modules.auth.routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/books",
    tags=["Books"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=APIResponse, summary="List semua book")
def list_books(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Cari berdasarkan name, judul, atau penerbit"),
    sort_by: str = Query("id", description="Kolom untuk sorting: id, name, judul, penerbit, created_at, updated_at"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Urutan sorting"),
    db: Session = Depends(get_db),
):
    """Ambil daftar book dengan paginasi."""
    items, total = service.get_book_list(
        db, skip=skip, limit=limit, search=search, sort_by=sort_by, sort_order=sort_order
    )
    return StandardJSONResponse.success(
        data=[BookResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} book.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get book by ID")
def get_book(id: int, db: Session = Depends(get_db)):
    """Ambil detail book berdasarkan ID."""
    item = service.get_book_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Book tidak ditemukan.")
    return StandardJSONResponse.success(
        data=BookResponse.model_validate(item),
        message="Book berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create book")
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    """Buat book baru."""
    try:
        item = service.create_book(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Book dengan data tersebut sudah ada.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal membuat book, silakan coba lagi.")
    return StandardJSONResponse.success(
        data=BookResponse.model_validate(item),
        message="Book berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update book")
def update_book(id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    """Update book berdasarkan ID."""
    try:
        item = service.update_book(db, id, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Update menyebabkan konflik data.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal mengupdate book, silakan coba lagi.")
    if not item:
        raise HTTPException(status_code=404, detail="Book tidak ditemukan.")
    return StandardJSONResponse.success(
        data=BookResponse.model_validate(item),
        message="Book berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete book")
def delete_book(id: int, db: Session = Depends(get_db)):
    """Soft-delete book berdasarkan ID."""
    success = service.delete_book(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Book tidak ditemukan.")
    return StandardJSONResponse.success(message="Book berhasil dihapus.")


# Summary provider for aggregator
def get_book_summary(db, _redis=None):
    """Return summary data for the book module."""
    try:
        _, total = service.get_book_list(
            db,
            skip=0,
            limit=1,
        )
    except SQLAlchemyError:
        logger.exception("Gagal mengambil summary book")
        total = 0

    return {
        "counts": {
            "book": total
        },
        "meta": {
            "module": "book"
        }
    }