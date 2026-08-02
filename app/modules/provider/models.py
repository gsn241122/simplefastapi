from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class Provider(Base):
    """SQLAlchemy model untuk Provider."""

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    api_url = Column(String(500), nullable=True)
    api_key_name = Column(String(100), nullable=True)
    config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Provider(id={self.id}, name={self.name!r})>"
