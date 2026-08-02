from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.payment.models import Payment
from app.modules.payment.schemas import PaymentCreate, PaymentUpdate


def get_payment_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Payment], int]:
    query = db.query(Payment).filter(Payment.status == "pending")

    if search:
        query = query.filter(Payment.payment_method.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_payment_by_id(db: Session, payment_id: int) -> Optional[Payment]:
    return db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.status == "pending",
    ).first()


def create_payment(db: Session, payload: PaymentCreate) -> Payment:
    db_payment = Payment(**payload.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


def update_payment(
    db: Session,
    payment_id: int,
    payload: PaymentUpdate,
) -> Optional[Payment]:
    db_payment = get_payment_by_id(db, payment_id)
    if not db_payment:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_payment, key, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment


def delete_payment(db: Session, payment_id: int) -> bool:
    db_payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not db_payment:
        return False

    db_payment.status = "deleted"
    db.commit()
    return True
