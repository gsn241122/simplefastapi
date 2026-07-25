from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.invoice.models import Invoice
from app.modules.invoice.schemas import InvoiceCreate, InvoiceUpdate


def get_invoice_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Invoice], int]:
    """
    Ambil daftar invoice dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Invoice, total count).
    """
    query = db.query(Invoice).filter(Invoice.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Invoice.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_invoice_by_id(db: Session, invoice_id: int) -> Optional[Invoice]:
    """Ambil satu invoice berdasarkan ID."""
    return db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_active == True,  # noqa: E712
    ).first()


def create_invoice(db: Session, payload: InvoiceCreate) -> Invoice:
    """Buat invoice baru."""
    db_item = Invoice(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_invoice(
    db: Session,
    invoice_id: int,
    payload: InvoiceUpdate,
) -> Optional[Invoice]:
    """Update invoice berdasarkan ID."""
    db_item = get_invoice_by_id(db, invoice_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_invoice(db: Session, invoice_id: int) -> bool:
    """Soft-delete invoice berdasarkan ID."""
    db_item = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
