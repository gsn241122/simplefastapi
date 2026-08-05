from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import get_db
from app.core.responses import APIResponse, StandardJSONResponse
from app.modules.message import service
from app.modules.message.schemas import MessageCreate, MessageResponse
from app.modules.auth.routes import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["Messages"], dependencies=[Depends(get_current_user)])

@router.get("", response_model=APIResponse, summary="List pesan dalam conversation")
def list_messages(conversation_id: int, db: Session = Depends(get_db)):
    messages = service.get_messages_by_conversation(db, conversation_id)
    return StandardJSONResponse.success(
        data=[MessageResponse.model_validate(m) for m in messages],
        message="Berhasil mengambil riwayat pesan."
    )

@router.post("", response_model=APIResponse, status_code=201, summary="Tambah pesan ke conversation")
def create_message(conversation_id: int, payload: MessageCreate, db: Session = Depends(get_db)):
    # Pastikan conversation_id di payload sesuai dengan path
    payload.conversation_id = conversation_id
    message = service.create_message(db, payload)
    return StandardJSONResponse.success(
        data=MessageResponse.model_validate(message),
        message="Pesan berhasil disimpan."
    )


# Summary provider for aggregator
def get_summary(db: Session, _redis=None):
    """Return summary data for the message module."""
    try:
        total = db.query(service.Message).count()
    except SQLAlchemyError:
        logger.exception("Gagal mengambil summary message")
        total = 0

    return {
        "counts": {
            "messages": total
        },
        "meta": {
            "module": "message"
        }
    }
