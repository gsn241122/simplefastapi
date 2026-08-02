from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.book.models import Book
from app.modules.book.schemas import BookCreate, BookUpdate


def get_book_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Book], int]:
    """
    Ambil daftar book dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Book, total count).
    """
    query = db.query(Book).filter(Book.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Book.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_book_by_id(db: Session, book_id: int) -> Optional[Book]:
    """Ambil satu book berdasarkan ID."""
    return db.query(Book).filter(
        Book.id == book_id,
        Book.is_active == True,  # noqa: E712
    ).first()


def create_book(db: Session, payload: BookCreate) -> Book:
    """Buat book baru."""
    db_item = Book(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_book(
    db: Session,
    book_id: int,
    payload: BookUpdate,
) -> Optional[Book]:
    """Update book berdasarkan ID."""
    db_item = get_book_by_id(db, book_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_book(db: Session, book_id: int) -> bool:
    """Soft-delete book berdasarkan ID."""
    db_item = db.query(Book).filter(Book.id == book_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
