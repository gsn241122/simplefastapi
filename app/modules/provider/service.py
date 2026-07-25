from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.provider.models import Provider
from app.modules.provider.schemas import ProviderCreate, ProviderUpdate


def get_provider_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Provider], int]:
    """
    Ambil daftar provider dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Provider, total count).
    """
    query = db.query(Provider).filter(Provider.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Provider.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_provider_by_id(db: Session, provider_id: int) -> Optional[Provider]:
    """Ambil satu provider berdasarkan ID."""
    return db.query(Provider).filter(
        Provider.id == provider_id,
        Provider.is_active == True,  # noqa: E712
    ).first()


def create_provider(db: Session, payload: ProviderCreate) -> Provider:
    """Buat provider baru."""
    db_item = Provider(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_provider(
    db: Session,
    provider_id: int,
    payload: ProviderUpdate,
) -> Optional[Provider]:
    """Update provider berdasarkan ID."""
    db_item = get_provider_by_id(db, provider_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_provider(db: Session, provider_id: int) -> bool:
    """Soft-delete provider berdasarkan ID."""
    db_item = db.query(Provider).filter(Provider.id == provider_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
