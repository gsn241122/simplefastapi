from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.customer import service
from app.modules.customer.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)

from app.modules.auth.routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=APIResponse, summary="List semua customer")
def list_customers(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    sort_by: str = Query("id", description="Kolom untuk sorting"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Urutan sorting"),
    db: Session = Depends(get_db),
):
    """Ambil daftar customer dengan paginasi."""
    items, total = service.get_customer_list(
        db, skip=skip, limit=limit, search=search, sort_by=sort_by, sort_order=sort_order
    )
    return StandardJSONResponse.success(
        data=[CustomerResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} customer.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get customer by ID")
def get_customer(id: int, db: Session = Depends(get_db)):
    """Ambil detail customer berdasarkan ID."""
    item = service.get_customer_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan.")
    return StandardJSONResponse.success(
        data=CustomerResponse.model_validate(item),
        message="Customer berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create customer")
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Buat customer baru."""
    try:
        item = service.create_customer(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Customer dengan data tersebut sudah ada.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal membuat customer, silakan coba lagi.")
    return StandardJSONResponse.success(
        data=CustomerResponse.model_validate(item),
        message="Customer berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update customer")
def update_customer(id: int, payload: CustomerUpdate, db: Session = Depends(get_db)):
    """Update customer berdasarkan ID."""
    try:
        item = service.update_customer(db, id, payload)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Update menyebabkan konflik data.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Gagal mengupdate customer, silakan coba lagi.")
    if not item:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan.")
    return StandardJSONResponse.success(
        data=CustomerResponse.model_validate(item),
        message="Customer berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete customer")
def delete_customer(id: int, db: Session = Depends(get_db)):
    """Soft-delete customer berdasarkan ID."""
    success = service.delete_customer(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan.")
    return StandardJSONResponse.success(message="Customer berhasil dihapus.")


# Summary provider for aggregator
def get_summary(db, _redis=None):
    """Return summary data for the customer module."""
    try:
        _, total = service.get_customer_list(
            db,
            skip=0,
            limit=1,
        )
    except SQLAlchemyError:
        logger.exception("Gagal mengambil summary customer")
        total = 0

    return {
        "counts": {
            "customers": total
        },
        "meta": {
            "module": "customer"
        }
    }
