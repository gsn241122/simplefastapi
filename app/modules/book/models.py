from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.sql import func

from app.core.database import Base


class Book(Base):
    """SQLAlchemy model untuk Book."""

    __tablename__ = "books"
    __table_args__ = (
        # Speeds up the common "list active books" query used by get_book_list.
        Index("ix_books_is_active_id", "is_active", "id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    # NOTE: previously unbounded String columns — MySQL requires an explicit
    # length for VARCHAR, and unbounded TEXT-like columns can't be indexed
    # efficiently. Bounded to match schemas.py validation.
    judul = Column(String(255), nullable=True, index=True)
    penerbit = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Book(id={self.id}, name={self.name!r}, is_active={self.is_active})>"