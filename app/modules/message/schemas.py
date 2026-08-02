from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class MessageBase(BaseModel):
    """Schema dasar untuk Message."""
    role: str = Field(..., description="Role pesan: user, assistant, system, tool")
    content: Optional[str] = Field(None, description="Isi pesan")
    tool_calls: Optional[Any] = Field(None, description="Data tool calls")
    tool_outputs: Optional[Any] = Field(None, description="Data output tool")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Metrik performa (tokens, latency, dll)")


class MessageCreate(MessageBase):
    """Schema untuk membuat pesan baru."""
    conversation_id: int


class MessageResponse(MessageBase):
    """Schema response untuk pesan."""
    id: int
    conversation_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
