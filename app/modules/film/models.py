from __future__ import annotations

from sqlalchemy import Column, Boolean, DateTime, Float, Integer, String, Index
from sqlalchemy.sql import func

from app.core.database import Base


class Film(Base):
    """SQLAlchemy model untuk Film."""

    __tablename__ = "films"
    __table_args__ = (
        Index("ix_films_is_active_id", "is_active", "id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    genre = Column(String(255), nullable=True)
    director = Column(String(255), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    release_date = Column(DateTime(timezone=True), nullable=True)
    rating = Column(Float, nullable=True)
    synopsis = Column(String(2000), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Film(id={self.id}, name={self.name!r}, is_active={self.is_active})>"
