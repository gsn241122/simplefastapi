from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Message(Base):
    """SQLAlchemy model untuk Message (Chat History)."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=True)
    
    # Support for Tool Calls
    tool_calls = Column(JSON, nullable=True)   # List of tool calls requested
    tool_outputs = Column(JSON, nullable=True) # Output from tool execution
    
    # Support for Metrics (latency, token usage, etc.)
    metrics = Column(JSON, nullable=True)      # {"tokens": 120, "latency_ms": 450, "cost": 0.001}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", backref="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role!r})>"
