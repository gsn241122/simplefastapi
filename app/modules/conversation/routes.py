from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.conversation import service
from app.modules.conversation.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua conversation")
def list_conversations(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Ambil daftar conversation dengan paginasi."""
    items, total = service.get_conversation_list(db, skip=skip, limit=limit, search=search)
    return StandardJSONResponse.success(
        data=[ConversationResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} conversation.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get conversation by ID")
def get_conversation(id: int, db: Session = Depends(get_db)):
    """Ambil detail conversation berdasarkan ID."""
    item = service.get_conversation_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Conversation tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ConversationResponse.model_validate(item),
        message="Conversation berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create conversation")
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    """Buat conversation baru."""
    item = service.create_conversation(db, payload)
    return StandardJSONResponse.success(
        data=ConversationResponse.model_validate(item),
        message="Conversation berhasil dibuat.",
    )


@router.put("/{id}", response_model=APIResponse, summary="Update conversation")
def update_conversation(id: int, payload: ConversationUpdate, db: Session = Depends(get_db)):
    """Update conversation berdasarkan ID."""
    item = service.update_conversation(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Conversation tidak ditemukan.")
    return StandardJSONResponse.success(
        data=ConversationResponse.model_validate(item),
        message="Conversation berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete conversation")
def delete_conversation(id: int, db: Session = Depends(get_db)):
    """Soft-delete conversation berdasarkan ID."""
    success = service.delete_conversation(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation tidak ditemukan.")
    return StandardJSONResponse.success(message="Conversation berhasil dihapus.")


# Summary provider for aggregator
def get_summary(db, redis=None):
    """Return a small summary dict for the conversation module."""
    try:
        _, total = service.get_conversation_list(db, skip=0, limit=1)
    except Exception:
        total = 0
    return {"counts": {"conversations": total}, "meta": {"module": "conversation"}}
