from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


def _strip_or_none(v: Optional[str]) -> Optional[str]:
    """Strip whitespace; convert empty/whitespace-only strings to None."""
    if v is None:
        return v
    v = v.strip()
    return v or None


class FilmBase(BaseModel):
    """Schema dasar untuk Film."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama film")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi film")
    genre: Optional[str] = Field(None, max_length=255)
    director: Optional[str] = Field(None, max_length=255)
    duration_minutes: Optional[int] = None
    release_date: Optional[datetime] = None
    rating: Optional[float] = None
    synopsis: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name tidak boleh kosong atau hanya berisi spasi")
        return v

    @field_validator("description", "genre", "director", "synopsis")
    @classmethod
    def strip_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class FilmCreate(FilmBase):
    """Schema untuk membuat Film baru."""
    pass


class FilmUpdate(BaseModel):
    """Schema untuk mengupdate Film (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    genre: Optional[str] = Field(None, max_length=255)
    director: Optional[str] = Field(None, max_length=255)
    duration_minutes: Optional[int] = None
    release_date: Optional[datetime] = None
    rating: Optional[float] = None
    synopsis: Optional[str] = Field(None, max_length=2000)

    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name tidak boleh kosong atau hanya berisi spasi")
        return v

    @field_validator("description", "genre", "director", "synopsis")
    @classmethod
    def strip_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class FilmResponse(FilmBase):
    """Schema response untuk Film."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
