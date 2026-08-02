from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.order.models import Order, OrderItem
from app.modules.order.schemas import OrderCreate, OrderUpdate
from app.modules.product.models import Product


def get_order_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Order], int]:
    query = db.query(Order).filter(Order.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Order.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(
        Order.id == order_id,
        Order.is_active == True,  # noqa: E712
    ).first()


def create_order(db: Session, payload: OrderCreate, user_id: Optional[int] = None) -> Order:
    """Buat order baru beserta item produknya dan hitung otomatis total harga."""
    calculated_amount = 0
    order_items_to_create = []

    for item_data in payload.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise ValueError(f"Produk dengan ID {item_data.product_id} tidak ditemukan.")
        
        item_price = product.price
        subtotal = int(item_price * item_data.quantity)
        calculated_amount += subtotal

        order_items_to_create.append(
            OrderItem(
                product_id=product.id,
                quantity=item_data.quantity,
                price=item_price
            )
        )

    tax = payload.tax_amount if payload.tax_amount > 0 else int(calculated_amount * 0.1)  # Default pajak 10% jika 0
    total = calculated_amount + tax

    db_order = Order(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        status=payload.status or "pending",
        amount=calculated_amount,
        tax_amount=tax,
        total_amount=total
    )
    db.add(db_order)
    db.flush()  # Dapatkan ID order sebelum commit

    for order_item in order_items_to_create:
        order_item.order_id = db_order.id
        db.add(order_item)

    db.commit()
    db.refresh(db_order)
    return db_order


def update_order(
    db: Session,
    order_id: int,
    payload: OrderUpdate,
) -> Optional[Order]:
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
    db_item = db.query(Order).filter(Order.id == order_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
