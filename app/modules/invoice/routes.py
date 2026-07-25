from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.invoice import service
from app.modules.invoice.schemas import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=APIResponse, summary="List semua invoice")
def list_invoices(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar invoice dengan paginasi."""
    items, total = service.get_invoice_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[InvoiceResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} invoice.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get invoice by ID")
def get_invoice(id: int, db: Session = Depends(get_db)):
    """Ambil detail invoice berdasarkan ID."""
    item = service.get_invoice_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan.")
    return StandardJSONResponse.success(
        data=InvoiceResponse.model_validate(item),
        message="Invoice berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create invoice")
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    """Buat invoice baru."""
    item = service.create_invoice(db, payload)
    return StandardJSONResponse.success(
        data=InvoiceResponse.model_validate(item),
        message="Invoice berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update invoice")
def update_invoice(id: int, payload: InvoiceUpdate, db: Session = Depends(get_db)):
    """Update invoice berdasarkan ID."""
    item = service.update_invoice(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan.")
    return StandardJSONResponse.success(
        data=InvoiceResponse.model_validate(item),
        message="Invoice berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete invoice")
def delete_invoice(id: int, db: Session = Depends(get_db)):
    """Soft-delete invoice berdasarkan ID."""
    success = service.delete_invoice(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Invoice tidak ditemukan.")
    return StandardJSONResponse.success(message="Invoice berhasil dihapus.")
