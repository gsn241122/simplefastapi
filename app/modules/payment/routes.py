from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.payment import service
from app.modules.payment.schemas import (
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/payments", tags=["Payments"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua payment")
def list_payments(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    items, total = service.get_payment_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[PaymentResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} payment.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get payment by ID")
def get_payment(id: int, db: Session = Depends(get_db)):
    item = service.get_payment_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Payment tidak ditemukan.")
    return StandardJSONResponse.success(
        data=PaymentResponse.model_validate(item),
        message="Payment berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create payment")
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)):
    item = service.create_payment(db, payload)
    return StandardJSONResponse.success(
        data=PaymentResponse.model_validate(item),
        message="Payment berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update payment")
def update_payment(id: int, payload: PaymentUpdate, db: Session = Depends(get_db)):
    item = service.update_payment(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Payment tidak ditemukan.")
    return StandardJSONResponse.success(
        data=PaymentResponse.model_validate(item),
        message="Payment berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete payment")
def delete_payment(id: int, db: Session = Depends(get_db)):
    success = service.delete_payment(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Payment tidak ditemukan.")
    return StandardJSONResponse.success(message="Payment berhasil dihapus.")
