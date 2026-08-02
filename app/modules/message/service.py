from sqlalchemy.orm import Session
from app.modules.message.models import Message
from app.modules.message.schemas import MessageCreate
from typing import List

def get_messages_by_conversation(db: Session, conversation_id: int) -> List[Message]:
    """Ambil riwayat pesan berdasarkan conversation_id."""
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()

def create_message(db: Session, payload: MessageCreate) -> Message:
    """Simpan pesan baru ke database."""
    db_message = Message(**payload.model_dump())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message
