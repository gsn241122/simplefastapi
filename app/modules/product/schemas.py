from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ProductBase(BaseModel):
    """Field dasar yang digunakan oleh semua product schema."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nama produk",
        example="Laptop Gaming ASUS ROG",
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Deskripsi produk",
        example="Laptop gaming dengan GPU RTX 4070 dan RAM 32GB",
    )
    price: Decimal = Field(
        ...,
        ge=0,
        description="Harga produk dalam satuan mata uang",
        example="15999000.00",
    )
    stock: int = Field(
        default=0,
        ge=0,
        description="Jumlah stok produk",
        example=50,
    )
    is_available: bool = Field(
        default=True,
        description="Apakah produk tersedia untuk dijual",
        example=True,
    )

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        """Pastikan nama produk tidak hanya berisi whitespace."""
        if not v.strip():
            raise ValueError("Nama produk tidak boleh kosong.")
        return v.strip()


class ProductCreate(ProductBase):
    """Schema untuk membuat produk baru."""
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    """Schema untuk memperbarui produk (semua field opsional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200, example="Nama Baru")
    description: Optional[str] = Field(None, max_length=1000, example="Deskripsi baru")
    price: Optional[Decimal] = Field(None, ge=0, example="12999000.00")
    stock: Optional[int] = Field(None, ge=0, example=25)
    is_available: Optional[bool] = Field(None, example=True)
    image_url: Optional[str] = Field(None, description="URL or path to the product image", example="uploads/product_image.jpg")


class ProductResponse(ProductBase):
    """Schema untuk response data produk."""

    id: int = Field(..., description="ID unik produk", example=1)
    is_deleted: bool = Field(False, description="Apakah produk sudah dihapus (soft delete)")
    deleted_at: Optional[datetime] = Field(None, description="Waktu penghapusan produk")
    created_at: Optional[datetime] = Field(None, description="Waktu pembuatan produk")
    updated_at: Optional[datetime] = Field(None, description="Waktu terakhir diperbarui")
    image_url: Optional[str] = Field(None, description="URL or path to the product image", example="uploads/product_image.jpg")

    model_config = {"from_attributes": True}
