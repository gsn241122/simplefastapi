from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Optional

from app.modules.film.models import Film
from app.modules.film.schemas import FilmCreate, FilmUpdate

logger = logging.getLogger(__name__)

SORTABLE_FIELDS = {"created_at", "director", "duration_minutes", "genre", "id", "name", "rating", "release_date", "synopsis", "updated_at"}


def get_film_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    sort_by: str = "id",
    sort_order: str = "asc",
) -> tuple[list[Film], int]:
    """
    Ambil daftar film dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Film, total count).
    """
    query = db.query(Film).filter(Film.is_active == True)  # noqa: E712

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Film.name.ilike(like),
            Film.genre.ilike(like),
            Film.director.ilike(like),
            Film.synopsis.ilike(like),
        ))

    total = query.count()

    sort_column = getattr(Film, sort_by if sort_by in SORTABLE_FIELDS else "id")
    if sort_order.lower() == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    items = query.offset(skip).limit(limit).all()
    return items, total


def get_film_by_id(db: Session, film_id: int) -> Optional[Film]:
    """Ambil satu film (aktif) berdasarkan ID."""
    return db.query(Film).filter(
        Film.id == film_id,
        Film.is_active == True,  # noqa: E712
    ).first()


def create_film(db: Session, payload: FilmCreate) -> Film:
    """Buat film baru."""
    db_item = Film(**payload.model_dump())
    db.add(db_item)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal membuat film: %s", payload.name)
        raise
    db.refresh(db_item)
    return db_item


def update_film(
    db: Session,
    film_id: int,
    payload: FilmUpdate,
) -> Optional[Film]:
    """Update film (aktif) berdasarkan ID."""
    db_item = get_film_by_id(db, film_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal mengupdate film id=%s", film_id)
        raise
    db.refresh(db_item)
    return db_item


def delete_film(db: Session, film_id: int) -> bool:
    """
    Soft-delete film berdasarkan ID.

    Hanya menghapus film yang masih aktif — memanggil delete pada
    item yang sudah nonaktif (atau tidak ada) mengembalikan False.
    """
    db_item = get_film_by_id(db, film_id)
    if not db_item:
        return False

    db_item.is_active = False
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal menghapus film id=%s", film_id)
        raise
    return True
