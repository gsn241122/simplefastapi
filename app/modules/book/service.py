from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Optional

from app.modules.book.models import Book
from app.modules.book.schemas import BookCreate, BookUpdate

logger = logging.getLogger(__name__)

# Columns eligible for sorting via the list endpoint. Whitelisted to avoid
# passing arbitrary/unsafe column names through to getattr().
SORTABLE_FIELDS = {"id", "name", "judul", "penerbit", "created_at", "updated_at"}


def get_book_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    sort_by: str = "id",
    sort_order: str = "asc",
) -> tuple[list[Book], int]:
    """
    Ambil daftar book dengan paginasi dan pencarian.

    search mencocokkan name, judul, dan penerbit (case-insensitive).

    Returns:
        Tuple (list of Book, total count).
    """
    query = db.query(Book).filter(Book.is_active == True)  # noqa: E712

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Book.name.ilike(like),
                Book.judul.ilike(like),
                Book.penerbit.ilike(like),
            )
        )

    total = query.count()

    sort_column = getattr(Book, sort_by if sort_by in SORTABLE_FIELDS else "id")
    if sort_order.lower() == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    items = query.offset(skip).limit(limit).all()
    return items, total


def get_book_by_id(db: Session, book_id: int) -> Optional[Book]:
    """Ambil satu book (aktif) berdasarkan ID."""
    return db.query(Book).filter(
        Book.id == book_id,
        Book.is_active == True,  # noqa: E712
    ).first()


def create_book(db: Session, payload: BookCreate) -> Book:
    """Buat book baru."""
    db_item = Book(**payload.model_dump())
    db.add(db_item)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal membuat book: %s", payload.name)
        raise
    db.refresh(db_item)
    return db_item


def update_book(
    db: Session,
    book_id: int,
    payload: BookUpdate,
) -> Optional[Book]:
    """Update book (aktif) berdasarkan ID."""
    db_item = get_book_by_id(db, book_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal mengupdate book id=%s", book_id)
        raise
    db.refresh(db_item)
    return db_item


def delete_book(db: Session, book_id: int) -> bool:
    """
    Soft-delete book berdasarkan ID.

    Hanya menghapus book yang masih aktif — memanggil delete pada book
    yang sudah nonaktif (atau tidak ada) mengembalikan False, sehingga
    route mengembalikan 404 secara konsisten alih-alih "berhasil" pada
    percobaan hapus kedua kalinya.
    """
    db_item = get_book_by_id(db, book_id)
    if not db_item:
        return False

    db_item.is_active = False
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Gagal menghapus book id=%s", book_id)
        raise
    return True