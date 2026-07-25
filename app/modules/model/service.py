from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.model.models import Model
from app.modules.model.schemas import ModelCreate, ModelUpdate


def get_model_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Model], int]:
    """
    Ambil daftar model dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Model, total count).
    """
    query = db.query(Model).filter(Model.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Model.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_model_by_id(db: Session, model_id: int) -> Optional[Model]:
    """Ambil satu model berdasarkan ID."""
    return db.query(Model).filter(
        Model.id == model_id,
        Model.is_active == True,  # noqa: E712
    ).first()


def create_model(db: Session, payload: ModelCreate) -> Model:
    """Buat model baru."""
    db_item = Model(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_model(
    db: Session,
    model_id: int,
    payload: ModelUpdate,
) -> Optional[Model]:
    """Update model berdasarkan ID."""
    db_item = get_model_by_id(db, model_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_model(db: Session, model_id: int) -> bool:
    """Soft-delete model berdasarkan ID."""
    db_item = db.query(Model).filter(Model.id == model_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
