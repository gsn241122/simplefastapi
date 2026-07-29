from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from app.modules.product.models import Product
from app.modules.product.schemas import ProductCreate, ProductUpdate


def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()


def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
) -> tuple[list, int]:
    """Get paginated list of available products with optional search filter."""
    query = db.query(Product).filter(Product.is_deleted == False)  # noqa: E712
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def create_product(db: Session, product: ProductCreate):
    db_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        is_available=product.is_available,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, product_id: int, product_update: ProductUpdate):
    db_product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if db_product:
        update_data = product_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int):
    db_product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if db_product:
        db_product.is_deleted = True
        db_product.deleted_at = datetime.now(timezone.utc)
        db.commit()
    return db_product
