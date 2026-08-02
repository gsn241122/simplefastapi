from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.modules.order import service
from app.modules.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderUpdate,
)
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=APIResponse, summary="List semua order")
def list_orders(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by name"),
    status: str | None = Query(None, description="Filter by order status"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db),
):
    items, total = service.get_order_list(db, skip=skip, limit=limit, search=search, status=status, user_id=user_id)
    return StandardJSONResponse.success(
        data=[OrderResponse.model_validate(i) for i in items],
        message=f"Berhasil mengambil {len(items)} order.",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{id}", response_model=APIResponse, summary="Get order by ID")
def get_order(id: int, db: Session = Depends(get_db)):
    item = service.get_order_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan.")
    return StandardJSONResponse.success(
        data=OrderResponse.model_validate(item),
        message="Order berhasil ditemukan.",
    )


@router.post("", response_model=APIResponse, status_code=201, summary="Create order")
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Buat order baru beserta item produk."""
    try:
        user_id = getattr(current_user, "id", None)
        item = service.create_order(db, payload, user_id=user_id)
        return StandardJSONResponse.success(
            data=OrderResponse.model_validate(item),
            message="Order berhasil dibuat.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{id}", response_model=APIResponse, summary="Update order")
def update_order(id: int, payload: OrderUpdate, db: Session = Depends(get_db)):
    item = service.update_order(db, id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan.")
    return StandardJSONResponse.success(
        data=OrderResponse.model_validate(item),
        message="Order berhasil diupdate.",
    )


@router.delete("/{id}", response_model=APIResponse, summary="Delete order")
def delete_order(id: int, db: Session = Depends(get_db)):
    success = service.delete_order(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan.")
    return StandardJSONResponse.success(message="Order berhasil dihapus.")


# Summary provider for aggregator
def get_summary(db, redis=None):
    """Return a small summary dict for the order module."""
    try:
        _, total = service.get_order_list(db, skip=0, limit=1)
    except Exception:
        total = 0
    return {"counts": {"orders": total}, "meta": {"module": "order"}}
