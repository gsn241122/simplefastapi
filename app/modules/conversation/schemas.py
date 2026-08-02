from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConversationBase(BaseModel):
    """Schema dasar untuk Conversation."""

    name: str = Field(..., min_length=1, max_length=255, description="Nama conversation")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi conversation")
    model_id: int = Field(..., description="ID Model AI")
    provider_id: int = Field(..., description="ID Provider AI")


class ConversationCreate(ConversationBase):
    """Schema untuk membuat Conversation baru."""
    pass


class ConversationUpdate(BaseModel):
    """Schema untuk mengupdate Conversation (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class ConversationResponse(ConversationBase):
    """Schema response untuk Conversation."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_name: Optional[str] = None
    provider_name: Optional[str] = None

    model_config = {"from_attributes": True}
