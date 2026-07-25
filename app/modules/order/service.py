from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.order.models import Order
from app.modules.order.schemas import OrderCreate, OrderUpdate


def get_order_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Order], int]:
    """
    Ambil daftar order dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Order, total count).
    """
    query = db.query(Order).filter(Order.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Order.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    """Ambil satu order berdasarkan ID."""
    return db.query(Order).filter(
        Order.id == order_id,
        Order.is_active == True,  # noqa: E712
    ).first()


def create_order(db: Session, payload: OrderCreate) -> Order:
    """Buat order baru."""
    db_item = Order(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_order(
    db: Session,
    order_id: int,
    payload: OrderUpdate,
) -> Optional[Order]:
    """Update order berdasarkan ID."""
    db_item = get_order_by_id(db, order_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_order(db: Session, order_id: int) -> bool:
    """Soft-delete order berdasarkan ID."""
    db_item = db.query(Order).filter(Order.id == order_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
