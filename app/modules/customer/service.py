from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Optional

from app.modules.customer.models import Customer
from app.modules.customer.schemas import CustomerCreate, CustomerUpdate

logger = logging.getLogger(__name__)

SORTABLE_FIELDS = {"address", "city", "created_at", "email", "id", "name", "phone", "updated_at"}


def get_customer_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    sort_by: str = "id",
    sort_order: str = "asc",
) -> tuple[list[Customer], int]:
    """
    Ambil daftar customer dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Customer, total count).
    """
    query = db.query(Customer).filter(Customer.is_active == True)  # noqa: E712

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Customer.name.ilike(like),
            Customer.email.ilike(like),
            Customer.phone.ilike(like),
            Customer.address.ilike(like),
            Customer.city.ilike(like),
        ))

    total = query.count()

    sort_column = getattr(Customer, sort_by if sort_by in SORTABLE_FIELDS else "id")
    if sort_order.lower() == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    items = query.offset(skip).limit(limit).all()
    return items, total


def get_customer_by_id(db: Session, customer_id: int) -> Optional[Customer]:
    """Ambil satu customer (aktif) berdasarkan ID."""
    return db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_active == True,  # noqa: E712
    ).first()


def create_customer(db: Session, payload: CustomerCreate) -> Customer:
    """Buat customer baru."""
    db_item = Customer(**payload.model_dump())
    db.add(db_item)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal membuat customer: %s", payload.name)
        raise
    db.refresh(db_item)
    return db_item


def update_customer(
    db: Session,
    customer_id: int,
    payload: CustomerUpdate,
) -> Optional[Customer]:
    """Update customer (aktif) berdasarkan ID."""
    db_item = get_customer_by_id(db, customer_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal mengupdate customer id=%s", customer_id)
        raise
    db.refresh(db_item)
    return db_item


def delete_customer(db: Session, customer_id: int) -> bool:
    """
    Soft-delete customer berdasarkan ID.

    Hanya menghapus customer yang masih aktif — memanggil delete pada
    item yang sudah nonaktif (atau tidak ada) mengembalikan False.
    """
    db_item = get_customer_by_id(db, customer_id)
    if not db_item:
        return False

    db_item.is_active = False
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal menghapus customer id=%s", customer_id)
        raise
    return True
