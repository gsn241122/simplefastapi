from __future__ import annotations

from sqlalchemy.orm import Session
from typing import Optional

from app.modules.conversation.models import Conversation
from app.modules.conversation.schemas import ConversationCreate, ConversationUpdate


def get_conversation_list(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
) -> tuple[list[Conversation], int]:
    """
    Ambil daftar conversation dengan paginasi dan pencarian.

    Returns:
        Tuple (list of Conversation, total count).
    """
    query = db.query(Conversation).filter(Conversation.is_active == True)  # noqa: E712

    if search:
        query = query.filter(Conversation.name.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def get_conversation_by_id(db: Session, conversation_id: int) -> Optional[Conversation]:
    """Ambil satu conversation berdasarkan ID."""
    return db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_active == True,  # noqa: E712
    ).first()


def create_conversation(db: Session, payload: ConversationCreate) -> Conversation:
    """Buat conversation baru."""
    db_item = Conversation(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_conversation(
    db: Session,
    conversation_id: int,
    payload: ConversationUpdate,
) -> Optional[Conversation]:
    """Update conversation berdasarkan ID."""
    db_item = get_conversation_by_id(db, conversation_id)
    if not db_item:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """Soft-delete conversation berdasarkan ID."""
    db_item = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not db_item:
        return False

    db_item.is_active = False
    db.commit()
    return True
