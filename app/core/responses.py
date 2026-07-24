from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional, Generic, TypeVar, List
from datetime import datetime


T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Metadata untuk response yang menggunakan paginasi."""

    total: int = Field(..., description="Total jumlah item yang tersedia", json_schema_extra={"example": 100})
    skip: int = Field(..., description="Jumlah item yang dilewati (offset)", json_schema_extra={"example": 0})
    limit: int = Field(..., description="Jumlah item per halaman", json_schema_extra={"example": 20})
    page: int = Field(..., description="Halaman saat ini (1-indexed)", json_schema_extra={"example": 1})
    total_pages: int = Field(..., description="Total jumlah halaman", json_schema_extra={"example": 5})
    has_next: bool = Field(..., description="Apakah ada halaman berikutnya", json_schema_extra={"example": True})
    has_prev: bool = Field(..., description="Apakah ada halaman sebelumnya", json_schema_extra={"example": False})

    @classmethod
    def create(cls, total: int, skip: int, limit: int) -> "PaginationMeta":
        """
        Buat instance PaginationMeta dari parameter paginasi.

        Args:
            total: Total item di database.
            skip: Offset item.
            limit: Jumlah item per halaman.

        Returns:
            PaginationMeta instance yang terisi.
        """
        total_pages = max(1, -(-total // limit)) if limit > 0 else 1  # ceil division
        current_page = (skip // limit) + 1 if limit > 0 else 1
        return cls(
            total=total,
            skip=skip,
            limit=limit,
            page=current_page,
            total_pages=total_pages,
            has_next=skip + limit < total,
            has_prev=skip > 0,
        )


class APIResponse(BaseModel, Generic[T]):
    """Standard response wrapper untuk semua API endpoint."""

    success: bool = Field(
        default=True,
        description="Menunjukkan apakah request berhasil",
        json_schema_extra={"example": True},
    )
    message: str = Field(
        default="Operation completed successfully",
        description="Pesan yang bisa dibaca manusia",
        json_schema_extra={"example": "Data berhasil diambil"},
    )
    data: Optional[Any] = Field(
        default=None,
        description="Payload data response",
    )
    meta: Optional[PaginationMeta] = Field(
        default=None,
        description="Metadata paginasi (hanya ada di list endpoint)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp response (UTC)",
        json_schema_extra={"example": "2024-01-01T00:00:00"},
    )
    error: Optional[str] = Field(
        default=None,
        description="Pesan error jika success=False",
        json_schema_extra={"example": None},
    )

    model_config = {
        "from_attributes": True,
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }


class StandardJSONResponse:
    """Helper untuk membuat APIResponse yang konsisten."""

    @staticmethod
    def success(
        data: Any = None,
        message: str = "Operation completed successfully",
        meta: Optional[PaginationMeta] = None,
    ) -> APIResponse:
        """
        Buat response sukses.

        Args:
            data: Payload data yang akan dikembalikan.
            message: Pesan deskriptif.
            meta: Metadata paginasi opsional.

        Returns:
            APIResponse instance.
        """
        return APIResponse(
            success=True,
            message=message,
            data=data,
            meta=meta,
        )

    @staticmethod
    def error(
        message: str,
        status_code: int = 400,
        error_detail: Optional[str] = None,
    ) -> tuple[APIResponse, int]:
        """
        Buat response error.

        Args:
            message: Pesan error yang akan ditampilkan.
            status_code: HTTP status code.
            error_detail: Detail error teknis opsional.

        Returns:
            Tuple (APIResponse, status_code).
        """
        return (
            APIResponse(
                success=False,
                message=message,
                error=error_detail or message,
            ),
            status_code,
        )
